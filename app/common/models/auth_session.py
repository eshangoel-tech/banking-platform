"""Auth session model."""
import uuid

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.common.db.base import Base


class AuthSession(Base):
    """Auth session model representing user authentication sessions."""

    __tablename__ = "auth_sessions"

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
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    refresh_token_hash = Column(
        Text,
        nullable=False,
    )

    device_info = Column(
        String(255),
        nullable=True,
    )

    ip_address = Column(
        String(50),
        nullable=True,
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

    # Relationship
    user = relationship("User", backref="auth_sessions")
