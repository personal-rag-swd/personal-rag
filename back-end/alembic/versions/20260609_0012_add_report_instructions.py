"""add report additional_instructions and detail_level

Revision ID: 20260609_0012
Revises: 20260609_0011
Create Date: 2026-06-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260609_0012"
down_revision: str | Sequence[str] | None = "20260609_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notebook_report",
        sa.Column("additional_instructions", sa.Text(), nullable=True),
    )
    op.add_column(
        "notebook_report",
        sa.Column("detail_level", sa.String(16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("notebook_report", "detail_level")
    op.drop_column("notebook_report", "additional_instructions")
