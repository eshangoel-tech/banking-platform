"""Loan simulation model."""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, func, Index
from sqlalchemy.dialects.postgresql import UUID

from app.repository.base import Base


class LoanSimulation(Base):
    """Tracks loan simulation/slider behavior."""

    __tablename__ = "loan_simulations"
    __table_args__ = (
        Index("ix_loan_simulations_user_id", "user_id"),
        Index("ix_loan_simulations_session_id", "session_id"),
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
    )

    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="SET NULL"),
        nullable=True,
    )

    tested_amount = Column(
        Numeric(14, 2),
        nullable=False,
    )

    tested_tenure = Column(
        Integer,
        nullable=False,
    )

    calculated_emi = Column(
        Numeric(14, 2),
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )

