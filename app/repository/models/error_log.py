"""Error log model."""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, func, Index
from sqlalchemy.dialects.postgresql import UUID

from app.repository.base import Base


class ErrorLog(Base):
    """Application errors captured by the global exception handler."""

    __tablename__ = "error_logs"
    __table_args__ = (
        Index("ix_error_logs_request_id", "request_id"),
        Index("ix_error_logs_session_id", "session_id"),
        Index("ix_error_logs_user_id", "user_id"),
        Index("ix_error_logs_created_at", "created_at"),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    request_id = Column(
        UUID(as_uuid=True),
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

    path = Column(String(255), nullable=False)
    method = Column(String(10), nullable=False)

    error_message = Column(String(512), nullable=False)
    stack_trace = Column(String, nullable=False)

    created_at = Column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )

