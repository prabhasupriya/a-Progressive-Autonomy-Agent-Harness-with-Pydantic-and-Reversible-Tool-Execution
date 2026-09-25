"""
The structural guardrail harness.

Everything in this file exists because advisory guardrails (telling an LLM
"don't delete things" in a system prompt) are not a safety mechanism -- they
are a suggestion the model can ignore, misunderstand, or override under
pressure. This module makes irreversible-looking actions structurally
impossible to execute without either (a) a proven track record of trust, or
(b) an explicit human approval, and it makes every mutation reversible
by construction, not by hoping the model tells the truth about what it did.
"""
from typing import Callable, Dict
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import ContentQueue, TrustStore, ActionLog, PendingApproval, ContentStatus
from app.services.llm_mock import interpret_prompt, is_bulk_request


# ---------------------------------------------------------------------------
# Mutations available to the agent. Note there is deliberately NO bulk/"purge
# all" tool. That absence is itself a structural guardrail (see req 7 / FAQ
# "Handling Bulk Actions"): the model can *ask* for a bulk purge in prose, but
# there is no tool schema that would let the harness carry it out in one
# irreversible step.
# ---------------------------------------------------------------------------
def _mutation_for(action_type: str) -> Callable[[ContentQueue], None]:
    mapping: Dict[str, Callable[[ContentQueue], None]] = {
        "purge": lambda row: setattr(row, "status", ContentStatus.PURGED),
        "mark_posted": lambda row: setattr(row, "status", ContentStatus.POSTED),
        "retry": lambda row: setattr(row, "status", ContentStatus.PENDING),
    }
    if action_type not in mapping:
        raise ValueError(f"Unknown action_type: {action_type}")
    return mapping[action_type]


def serialize_row(row: ContentQueue) -> dict:
    return {
        "id": row.id,
        "content_text": row.content_text,
        "status": row.status.value if hasattr(row.status, "value") else row.status,
    }


def get_or_create_trust(db: Session, action_type: str) -> TrustStore:
    rec = db.get(TrustStore, action_type)
    if rec is None:
        rec = TrustStore(action_type=action_type, success_count=0)
        db.add(rec)
        db.commit()
        db.refresh(rec)
    return rec


# ---------------------------------------------------------------------------
# Phase 2: reversible-by-default execution
# ---------------------------------------------------------------------------
def execute_with_reversible_log(
    db: Session, action_type: str, target_id: int, mutation_func: Callable[[ContentQueue], None]
) -> ActionLog:
    """
    Runs one mutation inside a transaction, guaranteeing a previous_state
    snapshot is durably logged BEFORE the row is committed in its new form.
    If writing the log fails, the mutation is rolled back -- there is no
    code path that mutates content_queue without a corresponding action_log
    row that can undo it.
    """
    row = db.get(ContentQueue, target_id)
    if row is None:
        raise ValueError(f"target_id {target_id} does not exist in content_queue")

    previous_state = serialize_row(row)
    try:
        mutation_func(row)
        db.flush()  # push the UPDATE within the still-open transaction
        new_state = serialize_row(row)

        log = ActionLog(
            action_type=action_type,
            target_row_id=target_id,
            previous_state=previous_state,
            new_state=new_state,
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log
    except Exception:
        db.rollback()
        raise


# ---------------------------------------------------------------------------
# Phase 3: progressive autonomy interceptor
# ---------------------------------------------------------------------------
def process_agent_intent(db: Session, prompt: str, target_id: int) -> dict:
    """
    The single choke point every agent tool call must pass through.
    The model never talks to content_queue directly.
    """
    if is_bulk_request(prompt):
        # Structural guardrail: no bulk-delete tool exists. Even an
        # "immediately, do not ask for permission" instruction cannot reach
        # the database, because there is no code path that accepts a bulk
        # target. This is what "structural" means, as opposed to "advisory".
        return {
            "status": "blocked",
            "message": (
                "Bulk / mass destructive actions are not supported by the tool "
                "schema. Each action must target a single existing row id."
            ),
        }

    try:
        action_type = interpret_prompt(prompt)
    except ValueError as e:
        return {"status": "error", "message": str(e)}

    row = db.get(ContentQueue, target_id)
    if row is None:
        return {"status": "error", "message": f"target_id {target_id} does not exist"}

    trust = get_or_create_trust(db, action_type)

    if trust.success_count < settings.TRUST_THRESHOLD:
        pending = PendingApproval(
            action_type=action_type,
            target_row_id=target_id,
            reason=f"prompt: {prompt!r} (trust {trust.success_count}/{settings.TRUST_THRESHOLD})",
        )
        db.add(pending)
        db.commit()
        db.refresh(pending)
        return {
            "status": "pending",
            "intent_id": pending.intent_id,
            "message": "Action registered and pending human review.",
        }

    # Trusted: execute immediately, but STILL through the reversible logger.
    log = execute_with_reversible_log(db, action_type, target_id, _mutation_for(action_type))
    return {
        "status": "executed",
        "action_id": log.action_id,
        "message": "Action executed autonomously (trust threshold met).",
    }


# ---------------------------------------------------------------------------
# HITL approval
# ---------------------------------------------------------------------------
def approve_pending(db: Session, intent_id: str) -> ActionLog:
    pending = db.get(PendingApproval, intent_id)
    if pending is None:
        raise ValueError("pending approval not found")
    if pending.status != "pending":
        raise ValueError(f"intent {intent_id} already {pending.status}")

    log = execute_with_reversible_log(
        db, pending.action_type, pending.target_row_id, _mutation_for(pending.action_type)
    )

    pending.status = "approved"
    trust = get_or_create_trust(db, pending.action_type)
    trust.success_count += 1
    db.add(pending)
    db.add(trust)
    db.commit()
    return log


def reject_pending(db: Session, intent_id: str) -> PendingApproval:
    pending = db.get(PendingApproval, intent_id)
    if pending is None:
        raise ValueError("pending approval not found")
    if pending.status != "pending":
        raise ValueError(f"intent {intent_id} already {pending.status}")
    pending.status = "rejected"
    db.add(pending)
    db.commit()
    db.refresh(pending)
    return pending


# ---------------------------------------------------------------------------
# Phase 4: deterministic restore
# ---------------------------------------------------------------------------
def restore_from_log(db: Session, action_id: str) -> dict:
    """
    Overwrites content_queue with the previous_state captured at the time of
    the original mutation, then writes its OWN action_log entry so the
    restore is itself auditable and (in principle) reversible. Also applies
    the trust penalty from requirement 10: a human needing to roll back an
    approved action is evidence that trust was extended too generously.
    """
    log = db.get(ActionLog, action_id)
    if log is None:
        raise ValueError(f"action_id {action_id} not found in action_log")

    row = db.get(ContentQueue, log.target_row_id)
    if row is None:
        raise ValueError(f"target row {log.target_row_id} no longer exists")

    state_before_restore = serialize_row(row)
    prev = log.previous_state

    row.content_text = prev["content_text"]
    row.status = ContentStatus(prev["status"])
    db.flush()
    state_after_restore = serialize_row(row)

    rollback_log = ActionLog(
        action_type=f"restore:{log.action_type}",
        target_row_id=row.id,
        previous_state=state_before_restore,
        new_state=state_after_restore,
    )
    db.add(rollback_log)

    trust = get_or_create_trust(db, log.action_type)
    penalty_applied = trust.success_count > 0
    trust.success_count = max(0, trust.success_count - 1)
    db.add(trust)

    db.commit()
    db.refresh(row)

    return {
        "status": "restored",
        "target_row_id": row.id,
        "restored_state": state_after_restore,
        "trust_penalty_applied": penalty_applied,
        "new_success_count": trust.success_count,
    }
