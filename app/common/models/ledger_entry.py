"""Ledger entry model."""
import uuid

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.common.db.base import Base


class LedgerEntry(Base):
    """
    Ledger entry model representing account transactions.
    
    ⚠️ IMPORTANT: This table is append-only.
    No updates or deletes are allowed. Ever.
    """

    __tablename__ = "ledger_entries"

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

    account_id = Column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    amount = Column(
        Numeric(14, 2),
        nullable=False,
    )

    currency = Column(
        String(5),
        nullable=False,
        default="INR",
        server_default="INR",
    )

    entry_type = Column(
        String(20),
        nullable=False,
    )

    reference_type = Column(
        String(30),
        nullable=True,
    )

    reference_id = Column(
        BigInteger,
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

    # Relationship
    account = relationship("Account", backref="ledger_entries")
