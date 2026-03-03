"""add_transfers_and_otp_reference_id

Revision ID: c7d8e9f0a1b2
Revises: f3a9c1d2e4b5
Create Date: 2026-03-02 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, Sequence[str], None] = "f3a9c1d2e4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # otp_verifications: add reference_id (nullable UUID)
    # Links a TRANSFER OTP to its specific transfer record
    # ------------------------------------------------------------------
    op.add_column(
        "otp_verifications",
        sa.Column("reference_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_otp_verifications_reference_id",
        "otp_verifications",
        ["reference_id"],
    )

    # ------------------------------------------------------------------
    # transfers table
    # ------------------------------------------------------------------
    op.create_table(
        "transfers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "sender_account_id",
            UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "receiver_account_id",
            UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="PENDING",
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
        "ix_transfers_sender_account_id", "transfers", ["sender_account_id"]
    )
    op.create_index(
        "ix_transfers_receiver_account_id", "transfers", ["receiver_account_id"]
    )
    op.create_index("ix_transfers_created_at", "transfers", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_transfers_created_at", table_name="transfers")
    op.drop_index("ix_transfers_receiver_account_id", table_name="transfers")
    op.drop_index("ix_transfers_sender_account_id", table_name="transfers")
    op.drop_table("transfers")

    op.drop_index(
        "ix_otp_verifications_reference_id", table_name="otp_verifications"
    )
    op.drop_column("otp_verifications", "reference_id")
