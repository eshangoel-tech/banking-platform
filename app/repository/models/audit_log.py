"""Audit log model."""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, func, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.repository.base import Base


class AuditLog(Base):
    """Business/audit events (LOGIN_SUCCESS, MONEY_CREDITED, etc.)."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_session_id", "session_id"),
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_event_type", "event_type"),
        Index("ix_audit_logs_created_at", "created_at"),
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

    event_type = Column(String(64), nullable=False)

    # Additional structured data about the event
    event_metadata = Column(JSONB, nullable=True)

    created_at = Column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )

