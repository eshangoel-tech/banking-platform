"""Session model."""
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, func, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.repository.base import Base


class Session(Base):
    """User session (for auth and audit)."""

    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_expires_at", "expires_at"),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Minimal non-sensitive metadata snapshot
    session_meta = Column(JSONB, nullable=True)

    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(255), nullable=True)

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    expires_at = Column(
        DateTime(timezone=False),
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )

    user = relationship("User", back_populates="sessions")

