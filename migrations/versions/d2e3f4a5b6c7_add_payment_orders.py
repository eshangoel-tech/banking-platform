"""add_payment_orders

Revision ID: d2e3f4a5b6c7
Revises: c7d8e9f0a1b2
Create Date: 2026-03-02 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, Sequence[str], None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_orders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "account_id",
            UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("razorpay_order_id", sa.String(64), unique=True, nullable=False),
        sa.Column("amount_requested", sa.Numeric(14, 2), nullable=False),
        sa.Column("amount_paid", sa.Numeric(14, 2), nullable=True),
        sa.Column(
            "currency",
            sa.String(8),
            nullable=False,
            server_default="INR",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="CREATED",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_payment_orders_user_id", "payment_orders", ["user_id"]
    )
    op.create_index(
        "ix_payment_orders_account_id", "payment_orders", ["account_id"]
    )
    op.create_index(
        "ix_payment_orders_razorpay_order_id",
        "payment_orders",
        ["razorpay_order_id"],
    )
    op.create_index(
        "ix_payment_orders_created_at", "payment_orders", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_payment_orders_created_at", table_name="payment_orders")
    op.drop_index(
        "ix_payment_orders_razorpay_order_id", table_name="payment_orders"
    )
    op.drop_index("ix_payment_orders_account_id", table_name="payment_orders")
    op.drop_index("ix_payment_orders_user_id", table_name="payment_orders")
    op.drop_table("payment_orders")
