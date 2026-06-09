"""add report status and error_message

Revision ID: 20260609_0011
Revises: 20260601_0010
Create Date: 2026-06-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260609_0011"
down_revision: str | Sequence[str] | None = "20260601_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notebook_report",
        sa.Column("status", sa.String(16), nullable=False, server_default="completed"),
    )
    op.add_column(
        "notebook_report",
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "ck_notebook_report_status_valid",
        "notebook_report",
        "status IN ('pending', 'generating', 'completed', 'failed', 'cancelled')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_notebook_report_status_valid", "notebook_report", type_="check"
    )
    op.drop_column("notebook_report", "error_message")
    op.drop_column("notebook_report", "status")
