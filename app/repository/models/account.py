"""Account model."""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.repository.base import Base


class Account(Base):
    """Bank account (one per user)."""

    __tablename__ = "accounts"
    __table_args__ = (
        # Enforce one account per user
        UniqueConstraint("user_id", name="uq_accounts_user_id"),
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

    account_number = Column(
        String(32),
        unique=True,
        nullable=False,
        index=True,
    )

    account_type = Column(
        String(20),
        nullable=False,
    )

    balance = Column(
        Numeric(14, 2),
        nullable=False,
        default=0,
        server_default="0",
    )

    currency = Column(
        String(8),
        nullable=False,
        default="INR",
        server_default="INR",
    )

    status = Column(
        String(20),
        nullable=False,
        default="ACTIVE",
        server_default="ACTIVE",
    )

    created_at = Column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user = relationship("User", back_populates="accounts")

