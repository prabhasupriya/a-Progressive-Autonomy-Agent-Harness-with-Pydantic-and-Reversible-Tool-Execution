from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import PendingApproval
from app.schemas.schemas import PendingApprovalOut, ApproveResponse
from app.services.harness import approve_pending, reject_pending, get_or_create_trust

router = APIRouter(prefix="/api/hitl", tags=["hitl"])


@router.get("/pending", response_model=List[PendingApprovalOut])
def list_pending(db: Session = Depends(get_db)):
    rows = (
        db.query(PendingApproval)
        .filter(PendingApproval.status == "pending")
        .order_by(PendingApproval.created_at.asc())
        .all()
    )
    return rows


@router.post("/approve/{intent_id}", response_model=ApproveResponse)
def approve(intent_id: str, db: Session = Depends(get_db)):
    try:
        log = approve_pending(db, intent_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    trust = get_or_create_trust(db, log.action_type)
    return ApproveResponse(
        status="executed",
        action_id=log.action_id,
        action_type=log.action_type,
        new_trust_success_count=trust.success_count,
    )


@router.post("/reject/{intent_id}")
def reject(intent_id: str, db: Session = Depends(get_db)):
    try:
        pending = reject_pending(db, intent_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "rejected", "intent_id": pending.intent_id}
