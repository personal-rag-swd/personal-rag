"""drop redundant indexes

Revision ID: 20260601_0008
Revises: 20260601_0007
Create Date: 2026-06-01
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260601_0008"
down_revision: str | Sequence[str] | None = "20260601_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_notebook_document_s3_key", table_name="notebook_document")
    op.drop_index("ix_notebook_report_report_type", table_name="notebook_report")
    op.drop_index("ix_notebook_message_seq", table_name="notebook_message")


def downgrade() -> None:
    op.create_index("ix_notebook_message_seq", "notebook_message", ["seq"], unique=False)
    op.create_index("ix_notebook_report_report_type", "notebook_report", ["report_type"], unique=False)
    op.create_index("ix_notebook_document_s3_key", "notebook_document", ["s3_key"], unique=False)
