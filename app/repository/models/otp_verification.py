"""OTP verification model."""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.repository.base import Base


class OtpVerification(Base):
    """OTP lifecycle tracking for login, payments, etc."""

    __tablename__ = "otp_verifications"
    __table_args__ = (
        Index("ix_otp_verifications_expires_at", "expires_at"),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    otp_hash = Column(String(255), nullable=False)

    otp_type = Column(String(32), nullable=False)

    attempts = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    max_attempts = Column(
        Integer,
        nullable=False,
        default=3,
        server_default="3",
    )

    expires_at = Column(
        DateTime(timezone=False),
        nullable=False,
    )

    status = Column(
        String(20),
        nullable=False,
        default="PENDING",
        server_default="PENDING",
    )

    created_at = Column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )

    user = relationship("User", backref="otp_verifications")

