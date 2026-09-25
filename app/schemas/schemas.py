from typing import Optional, Any, Dict
from pydantic import BaseModel, Field


class AgentExecuteRequest(BaseModel):
    prompt: str
    target_id: int


class ToolCallIntent(BaseModel):
    """What the (mock) LLM is allowed to hand back to the harness. The harness,
    not the model, decides whether this actually runs."""

    action_name: str = Field(..., description="One of: mark_posted, retry, purge")
    target_id: int = Field(..., description="The content_queue row this targets")
    reason: str = Field(default="", description="Why the model believes this is needed")


class AgentExecuteResponse(BaseModel):
    status: str  # pending | executed | blocked | error
    message: str
    intent_id: Optional[str] = None
    action_id: Optional[str] = None


class PendingApprovalOut(BaseModel):
    intent_id: str
    action_type: str
    target_row_id: int
    reason: Optional[str] = None
    status: str

    class Config:
        from_attributes = True


class ApproveResponse(BaseModel):
    status: str
    action_id: str
    action_type: str
    new_trust_success_count: int


class RestoreRequest(BaseModel):
    action_id: str


class RestoreResponse(BaseModel):
    status: str
    target_row_id: int
    restored_state: Dict[str, Any]
    trust_penalty_applied: bool
    new_success_count: Optional[int] = None
