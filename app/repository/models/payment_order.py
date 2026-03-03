"""PaymentOrder model — tracks Razorpay add-money transactions."""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, func, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.repository.base import Base


class PaymentOrder(Base):
    """
    Lifecycle: CREATED → SUCCESS | FAILED

    Created when the user requests an add-money session; updated by the
    Razorpay webhook once the payment is settled.
    """

    __tablename__ = "payment_orders"
    __table_args__ = (
        Index("ix_payment_orders_user_id", "user_id"),
        Index("ix_payment_orders_account_id", "account_id"),
        Index("ix_payment_orders_razorpay_order_id", "razorpay_order_id"),
        Index("ix_payment_orders_created_at", "created_at"),
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

    account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Razorpay order ID (e.g. "order_AbCdEfGhIjKlMn")
    razorpay_order_id = Column(
        String(64),
        unique=True,
        nullable=False,
    )

    # Amount the user requested to add (INR, not paise)
    amount_requested = Column(Numeric(14, 2), nullable=False)

    # Amount actually paid as confirmed by Razorpay (INR)
    amount_paid = Column(Numeric(14, 2), nullable=True)

    currency = Column(
        String(8),
        nullable=False,
        default="INR",
        server_default="INR",
    )

    status = Column(
        String(20),
        nullable=False,
        default="CREATED",
        server_default="CREATED",
    )

    created_at = Column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )

    completed_at = Column(DateTime(timezone=False), nullable=True)

    user = relationship("User", lazy="select")
    account = relationship("Account", lazy="select")
