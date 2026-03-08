"""error_log_message_to_text

Revision ID: e5f6a7b8c9d0
Revises: d2e3f4a5b6c7
Create Date: 2026-03-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "error_logs",
        "error_message",
        type_=sa.Text(),
        existing_type=sa.String(512),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "error_logs",
        "error_message",
        type_=sa.String(512),
        existing_type=sa.Text(),
        existing_nullable=False,
    )
