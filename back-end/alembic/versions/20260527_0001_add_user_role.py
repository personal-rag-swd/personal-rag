"""add user role

Revision ID: 20260527_0001
Revises: 858165ec030f
Create Date: 2026-05-27 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260527_0001"
down_revision: str | Sequence[str] | None = "858165ec030f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("role", sa.String(length=50), server_default="user", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("user", "role")
