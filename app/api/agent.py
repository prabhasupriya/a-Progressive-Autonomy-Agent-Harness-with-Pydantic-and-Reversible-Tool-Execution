from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.schemas import AgentExecuteRequest, AgentExecuteResponse
from app.services.harness import process_agent_intent

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/execute", response_model=AgentExecuteResponse)
def execute(req: AgentExecuteRequest, db: Session = Depends(get_db)):
    """
    Entry point the LLM orchestrator calls with its (mocked) tool-call
    intent. This endpoint NEVER mutates content_queue directly -- it always
    routes through process_agent_intent, which is the only thing that talks
    to the trust store and the reversible logger.
    """
    result = process_agent_intent(db, req.prompt, req.target_id)
    return AgentExecuteResponse(**result)
