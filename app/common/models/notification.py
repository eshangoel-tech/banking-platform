"""Notification model."""
import uuid

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.common.db.base import Base


class Notification(Base):
    """Notification model representing user communications."""

    __tablename__ = "notifications"

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

    channel = Column(
        String(20),
        nullable=False,
    )

    message = Column(
        Text,
        nullable=False,
    )

    status = Column(
        String(20),
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )

    # Relationship
    user = relationship("User", backref="notifications")
