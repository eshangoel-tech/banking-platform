"""External service log model."""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, func, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.repository.base import Base


class ExternalServiceLog(Base):
    """Logs calls to external services (payment gateway, SMTP, OpenAI, etc.)."""

    __tablename__ = "external_service_logs"
    __table_args__ = (
        Index("ix_external_service_logs_service_name", "service_name"),
        Index("ix_external_service_logs_status", "status"),
        Index("ix_external_service_logs_created_at", "created_at"),
        Index("ix_external_service_logs_session_id", "session_id"),
        Index("ix_external_service_logs_user_id", "user_id"),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    service_name = Column(String(64), nullable=False)

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

    request_payload = Column(JSONB, nullable=True)
    response_payload = Column(JSONB, nullable=True)

    status = Column(String(20), nullable=False)

    created_at = Column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )

