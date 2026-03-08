"""Chat session model — tracks a customer's AI chat session."""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, func, Index
from sqlalchemy.dialects.postgresql import UUID

from app.repository.base import Base


class ChatSession(Base):
    """
    One chat session per customer interaction with the AI assistant.

    Lifecycle: ACTIVE → CLOSED
    """

    __tablename__ = "chat_sessions"
    __table_args__ = (
        Index("ix_chat_sessions_session_id", "session_id"),
        Index("ix_chat_sessions_customer_id", "customer_id"),
        Index("ix_chat_sessions_status", "status"),
    )

    chat_sess_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    # FK to the banking auth session (sessions.id)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Human-readable customer identifier (string from users.customer_id)
    customer_id = Column(String(32), nullable=False)

    started_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    last_active = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ACTIVE | CLOSED
    status = Column(
        String(20),
        nullable=False,
        default="ACTIVE",
        server_default="ACTIVE",
    )
