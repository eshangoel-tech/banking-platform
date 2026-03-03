"""Transfer model — tracks internal money transfers between accounts."""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, func, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.repository.base import Base


class Transfer(Base):
    """
    Pending/completed internal transfer between two accounts.

    Lifecycle: PENDING → COMPLETED | FAILED
    """

    __tablename__ = "transfers"
    __table_args__ = (
        Index("ix_transfers_sender_account_id", "sender_account_id"),
        Index("ix_transfers_receiver_account_id", "receiver_account_id"),
        Index("ix_transfers_created_at", "created_at"),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    sender_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )

    receiver_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )

    amount = Column(
        Numeric(14, 2),
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

    completed_at = Column(
        DateTime(timezone=False),
        nullable=True,
    )

    sender_account = relationship(
        "Account", foreign_keys=[sender_account_id], lazy="select"
    )
    receiver_account = relationship(
        "Account", foreign_keys=[receiver_account_id], lazy="select"
    )
