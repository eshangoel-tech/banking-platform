"""Ledger entry model (financial source of truth)."""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, func, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.repository.base import Base


class LedgerEntry(Base):
    """
    Append-only ledger entry representing account transactions.
    """

    __tablename__ = "ledger_entries"
    __table_args__ = (
        Index("ix_ledger_entries_created_at", "created_at"),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    entry_type = Column(
        String(16),
        nullable=False,
    )

    amount = Column(
        Numeric(14, 2),
        nullable=False,
    )

    balance_after = Column(
        Numeric(14, 2),
        nullable=False,
    )

    reference_type = Column(
        String(32),
        nullable=True,
    )

    reference_id = Column(
        UUID(as_uuid=True),
        nullable=True,
    )

    description = Column(
        String(255),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )

    account = relationship("Account", backref="ledger_entries")

