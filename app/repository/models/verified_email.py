"""Verified email addresses that are allowed to register."""
import uuid

from sqlalchemy import Column, DateTime, String, func, Index
from sqlalchemy.dialects.postgresql import UUID

from app.repository.base import Base


class VerifiedEmail(Base):
    """Email addresses that have passed out-of-band verification."""

    __tablename__ = "verified_emails"
    __table_args__ = (
        Index("ix_verified_emails_email", "email"),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    email = Column(String(150), unique=True, nullable=False)

    created_at = Column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )

