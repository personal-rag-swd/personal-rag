"""add notebook chat history

Revision ID: 20260527_0003
Revises: 20260527_0002
Create Date: 2026-05-27 00:03:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260527_0003"
down_revision: str | Sequence[str] | None = "20260527_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    default = (
        sa.text("'[]'::jsonb")
        if op.get_bind().dialect.name == "postgresql"
        else sa.text("'[]'")
    )
    op.add_column(
        "notebook",
        sa.Column(
            "chat_history",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            server_default=default,
            nullable=False,
        ),
    )
    op.alter_column("notebook", "chat_history", server_default=None)


def downgrade() -> None:
    op.drop_column("notebook", "chat_history")
