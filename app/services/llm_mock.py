"""
Deliberately dumb, deterministic stand-in for an LLM tool-call step.

Automated evaluation cannot depend on a live model or an API key, and the
lesson of this exercise is about the HARNESS, not the model. This module's
only job is to turn free text into a ToolCallIntent, the same shape a real
LLM's structured tool-use output would take. Everything downstream (trust
checks, logging, execution) is identical whether this is a mock or a real
Claude/GPT call behind a Pydantic tool schema.

The model (mock or real) is NEVER told about trust counters or thresholds.
It just proposes an action; the harness silently gates it.
"""

BULK_KEYWORDS = [
    "everything",
    "all rows",
    "all posts",
    "entire queue",
    "bulk",
    "every row",
    "whole queue",
]

PURGE_KEYWORDS = ["purge", "delete", "remove", "clean", "corrupted", "stale"]
RETRY_KEYWORDS = ["retry", "resend", "re-send", "requeue"]
POST_KEYWORDS = ["post", "publish", "mark posted", "mark as posted"]


def is_bulk_request(prompt: str) -> bool:
    p = prompt.lower()
    return any(k in p for k in BULK_KEYWORDS)


def interpret_prompt(prompt: str) -> str:
    """Classify the requested action type from free text.

    This is intentionally naive keyword matching -- the whole point of the
    harness is that it does NOT matter how confidently or cleverly the model
    argues for an action; the structural gate downstream doesn't care.
    """
    p = prompt.lower()
    if any(k in p for k in PURGE_KEYWORDS):
        return "purge"
    if any(k in p for k in RETRY_KEYWORDS):
        return "retry"
    if any(k in p for k in POST_KEYWORDS):
        return "mark_posted"
    raise ValueError(
        "Could not interpret prompt into a known tool (mark_posted, retry, purge)."
    )
