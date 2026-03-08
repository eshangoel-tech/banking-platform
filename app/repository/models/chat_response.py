"""Chat response model — one turn (user message + assistant reply) per row."""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Text, func, Index
from sqlalchemy.dialects.postgresql import UUID

from app.repository.base import Base


class ChatResponse(Base):
    """Stores each conversational exchange within a chat session."""

    __tablename__ = "chat_responses"
    __table_args__ = (
        Index("ix_chat_responses_chat_sess_id", "chat_sess_id"),
        Index("ix_chat_responses_created_at", "created_at"),
    )

    response_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    chat_sess_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.chat_sess_id", ondelete="CASCADE"),
        nullable=False,
    )

    user_message = Column(Text, nullable=False)
    assistant_response = Column(Text, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
