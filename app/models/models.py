import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class ContentStatus(str, enum.Enum):
    PENDING = "PENDING"
    POSTED = "POSTED"
    FAILED = "FAILED"
    PURGED = "PURGED"


def _uuid() -> str:
    return str(uuid.uuid4())


class ContentQueue(Base):
    """The business data the agent is allowed to propose mutations against."""

    __tablename__ = "content_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_text = Column(String, nullable=False)
    status = Column(
        SAEnum(ContentStatus, name="content_status", native_enum=False, length=16),
        nullable=False,
        default=ContentStatus.PENDING,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class TrustStore(Base):
    """Per-action-type trust counters. Never exposed to the LLM's context."""

    __tablename__ = "trust_store"

    action_type = Column(String, primary_key=True)
    success_count = Column(Integer, nullable=False, default=0)


class ActionLog(Base):
    """Append-only ledger. Every mutation, and every restore, gets a row here."""

    __tablename__ = "action_log"

    action_id = Column(String, primary_key=True, default=_uuid)
    action_type = Column(String, nullable=False)
    target_row_id = Column(Integer, ForeignKey("content_queue.id"), nullable=False)
    previous_state = Column(JSON, nullable=True)
    new_state = Column(JSON, nullable=True)
    executed_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PendingApproval(Base):
    """Tool call intents parked here until a human approves or rejects them."""

    __tablename__ = "pending_approval"

    intent_id = Column(String, primary_key=True, default=_uuid)
    action_type = Column(String, nullable=False)
    target_row_id = Column(Integer, nullable=False)
    reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(String, nullable=False, default="pending")  # pending | approved | rejected
