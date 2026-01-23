"""Loan model."""
import uuid

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.common.db.base import Base


class Loan(Base):
    """Loan model representing loan contracts."""

    __tablename__ = "loans"

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

    loan_amount = Column(
        Numeric(14, 2),
        nullable=False,
    )

    processing_fee = Column(
        Numeric(14, 2),
        nullable=False,
        default=0.00,
        server_default="0.00",
    )

    tenure_months = Column(
        Integer,
        nullable=False,
    )

    interest_rate = Column(
        Numeric(5, 2),
        nullable=False,
    )

    status = Column(
        String(30),
        nullable=False,
    )

    approved_at = Column(
        DateTime(timezone=False),
        nullable=True,
    )

    closed_at = Column(
        DateTime(timezone=False),
        nullable=True,
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

    # Relationship
    user = relationship("User", backref="loans")
