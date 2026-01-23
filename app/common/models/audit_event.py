"""Audit event model."""
import uuid

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.common.db.base import Base


class AuditEvent(Base):
    """Audit event model representing compliance and security logs."""

    __tablename__ = "audit_events"

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        nullable=False,
    )

    uuid = Column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        default=uuid.uuid4,
        index=True,
    )

    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    event_type = Column(
        String(50),
        nullable=False,
        index=True,
    )

    event_data = Column(
        JSONB,
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )

    # Relationship
    user = relationship("User", backref="audit_events")
