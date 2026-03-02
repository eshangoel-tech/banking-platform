"""AI interaction logging model."""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func, Index
from sqlalchemy.dialects.postgresql import UUID

from app.repository.base import Base


class AIInteraction(Base):
    """Logs AI model interactions for traceability and cost tracking."""

    __tablename__ = "ai_interactions"
    __table_args__ = (
        Index("ix_ai_interactions_session_id", "session_id"),
        Index("ix_ai_interactions_user_id", "user_id"),
        Index("ix_ai_interactions_created_at", "created_at"),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="SET NULL"),
        nullable=True,
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    model_name = Column(String(128), nullable=False)
    prompt = Column(String, nullable=False)
    response = Column(String, nullable=False)

    tokens_used = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)

    created_at = Column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )

