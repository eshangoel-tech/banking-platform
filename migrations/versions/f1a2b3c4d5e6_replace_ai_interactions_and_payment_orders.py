"""replace_ai_interactions_and_payment_orders

Drop legacy ai_interactions and payment_orders tables.
Add chat_sessions, chat_responses, llm_interactions tables.

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-03-08 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Drop legacy tables
    # ------------------------------------------------------------------
    op.drop_index("ix_ai_interactions_created_at", table_name="ai_interactions")
    op.drop_index("ix_ai_interactions_session_id", table_name="ai_interactions")
    op.drop_index("ix_ai_interactions_user_id", table_name="ai_interactions")
    op.drop_table("ai_interactions")

    op.drop_index("ix_payment_orders_created_at", table_name="payment_orders")
    op.drop_index("ix_payment_orders_razorpay_order_id", table_name="payment_orders")
    op.drop_index("ix_payment_orders_account_id", table_name="payment_orders")
    op.drop_index("ix_payment_orders_user_id", table_name="payment_orders")
    op.drop_table("payment_orders")

    # ------------------------------------------------------------------
    # chat_sessions
    # ------------------------------------------------------------------
    op.create_table(
        "chat_sessions",
        sa.Column("chat_sess_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("customer_id", sa.String(32), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_active",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(20),
            server_default="ACTIVE",
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("chat_sess_id"),
    )
    op.create_index("ix_chat_sessions_session_id", "chat_sessions", ["session_id"])
    op.create_index("ix_chat_sessions_customer_id", "chat_sessions", ["customer_id"])
    op.create_index("ix_chat_sessions_status", "chat_sessions", ["status"])

    # ------------------------------------------------------------------
    # chat_responses
    # ------------------------------------------------------------------
    op.create_table(
        "chat_responses",
        sa.Column("response_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chat_sess_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_message", sa.Text(), nullable=False),
        sa.Column("assistant_response", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["chat_sess_id"],
            ["chat_sessions.chat_sess_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("response_id"),
    )
    op.create_index("ix_chat_responses_chat_sess_id", "chat_responses", ["chat_sess_id"])
    op.create_index("ix_chat_responses_created_at", "chat_responses", ["created_at"])

    # ------------------------------------------------------------------
    # llm_interactions
    # ------------------------------------------------------------------
    op.create_table(
        "llm_interactions",
        sa.Column("interaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("response_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_name", sa.String(128), nullable=False),
        sa.Column("request", sa.Text(), nullable=True),
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            server_default="SUCCESS",
            nullable=False,
        ),
        sa.Column("error_msg", sa.Text(), nullable=True),
        sa.Column("token_input", sa.Integer(), nullable=True),
        sa.Column("token_output", sa.Integer(), nullable=True),
        sa.Column("context_attached", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["response_id"],
            ["chat_responses.response_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("interaction_id"),
    )
    op.create_index("ix_llm_interactions_response_id", "llm_interactions", ["response_id"])
    op.create_index("ix_llm_interactions_agent_name", "llm_interactions", ["agent_name"])
    op.create_index("ix_llm_interactions_status", "llm_interactions", ["status"])
    op.create_index("ix_llm_interactions_created_at", "llm_interactions", ["created_at"])


def downgrade() -> None:
    # ------------------------------------------------------------------
    # Drop new tables (reverse order due to FKs)
    # ------------------------------------------------------------------
    op.drop_index("ix_llm_interactions_created_at", table_name="llm_interactions")
    op.drop_index("ix_llm_interactions_status", table_name="llm_interactions")
    op.drop_index("ix_llm_interactions_agent_name", table_name="llm_interactions")
    op.drop_index("ix_llm_interactions_response_id", table_name="llm_interactions")
    op.drop_table("llm_interactions")

    op.drop_index("ix_chat_responses_created_at", table_name="chat_responses")
    op.drop_index("ix_chat_responses_chat_sess_id", table_name="chat_responses")
    op.drop_table("chat_responses")

    op.drop_index("ix_chat_sessions_status", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_customer_id", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_session_id", table_name="chat_sessions")
    op.drop_table("chat_sessions")

    # ------------------------------------------------------------------
    # Restore legacy tables
    # ------------------------------------------------------------------
    op.create_table(
        "ai_interactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("model_name", sa.String(128), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_interactions_created_at", "ai_interactions", ["created_at"])
    op.create_index("ix_ai_interactions_session_id", "ai_interactions", ["session_id"])
    op.create_index("ix_ai_interactions_user_id", "ai_interactions", ["user_id"])

    op.create_table(
        "payment_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("razorpay_order_id", sa.String(64), unique=True, nullable=False),
        sa.Column("amount_requested", sa.Numeric(14, 2), nullable=False),
        sa.Column("amount_paid", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(8), server_default="INR", nullable=False),
        sa.Column("status", sa.String(20), server_default="CREATED", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=False), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payment_orders_created_at", "payment_orders", ["created_at"])
    op.create_index("ix_payment_orders_razorpay_order_id", "payment_orders", ["razorpay_order_id"])
    op.create_index("ix_payment_orders_account_id", "payment_orders", ["account_id"])
    op.create_index("ix_payment_orders_user_id", "payment_orders", ["user_id"])
