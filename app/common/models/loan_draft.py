"""Loan draft model."""
import uuid

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.common.db.base import Base


class LoanDraft(Base):
    """Loan draft model representing temporary loan configurations."""

    __tablename__ = "loan_drafts"

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

    draft_loan_amount = Column(
        Numeric(14, 2),
        nullable=False,
    )

    draft_tenure_months = Column(
        Integer,
        nullable=False,
    )

    last_modified_by = Column(
        String(20),
        nullable=True,
    )

    expires_at = Column(
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
    user = relationship("User", backref="loan_drafts")
