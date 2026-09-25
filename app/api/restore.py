from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.schemas import RestoreRequest, RestoreResponse
from app.services.harness import restore_from_log

router = APIRouter(prefix="/api/system", tags=["system"])


@router.post("/restore", response_model=RestoreResponse)
def restore(req: RestoreRequest, db: Session = Depends(get_db)):
    try:
        result = restore_from_log(db, req.action_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return RestoreResponse(**result)
