"""add notebook_report table

Revision ID: 20260529_0006
Revises: 20260528_0005
Create Date: 2026-05-29
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260529_0006"
down_revision: str | Sequence[str] | None = "20260528_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notebook_report",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("notebook_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("report_type", sa.String(32), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["notebook_id"], ["notebook.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notebook_report_notebook_id", "notebook_report", ["notebook_id"]
    )
    op.create_index("ix_notebook_report_user_id", "notebook_report", ["user_id"])
    op.create_index(
        "ix_notebook_report_report_type", "notebook_report", ["report_type"]
    )


def downgrade() -> None:
    op.drop_index("ix_notebook_report_report_type", table_name="notebook_report")
    op.drop_index("ix_notebook_report_user_id", table_name="notebook_report")
    op.drop_index("ix_notebook_report_notebook_id", table_name="notebook_report")
    op.drop_table("notebook_report")
