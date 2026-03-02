"""Request log model."""
import uuid

from sqlalchemy import Column, DateTime, Integer, String, func, Index, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.repository.base import Base


class RequestLog(Base):
    """Sanitized HTTP request/response logs."""

    __tablename__ = "request_logs"
    __table_args__ = (
        Index("ix_request_logs_request_id", "request_id"),
        Index("ix_request_logs_session_id", "session_id"),
        Index("ix_request_logs_user_id", "user_id"),
        Index("ix_request_logs_path", "path"),
        Index("ix_request_logs_created_at", "created_at"),
        Index(
            "ix_request_logs_request_id_created_at",
            "request_id",
            "created_at",
        ),
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

    method = Column(String(10), nullable=False)
    path = Column(String(255), nullable=False)
    status_code = Column(Integer, nullable=False)
    duration_ms = Column(Integer, nullable=False)

    request_body = Column(JSONB, nullable=True)
    response_body = Column(JSONB, nullable=True)

    error_message = Column(String(255), nullable=True)

    created_at = Column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )

