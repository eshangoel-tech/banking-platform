"""Loan model."""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.repository.base import Base


class Loan(Base):
    """Loan contracts for users."""

    __tablename__ = "loans"

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

    account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    principal_amount = Column(
        Numeric(14, 2),
        nullable=False,
    )

    interest_rate = Column(
        Numeric(5, 2),
        nullable=False,
    )

    tenure_months = Column(
        Integer,
        nullable=False,
    )

    emi_amount = Column(
        Numeric(14, 2),
        nullable=False,
    )

    outstanding_amount = Column(
        Numeric(14, 2),
        nullable=False,
    )

    status = Column(
        String(20),
        nullable=False,
    )

    approved_at = Column(DateTime(timezone=False), nullable=True)

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

    user = relationship("User", backref="loans")
    account = relationship("Account", backref="loans")

