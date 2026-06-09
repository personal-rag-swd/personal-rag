"""schema hardening constraints and query indexes

Revision ID: 20260601_0007
Revises: 20260529_0006
Create Date: 2026-06-01
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260601_0007"
down_revision: str | Sequence[str] | None = "20260529_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    duplicate = bind.execute(
        sa.text(
            """
            SELECT notebook_id, seq, COUNT(*)
            FROM notebook_message
            GROUP BY notebook_id, seq
            HAVING COUNT(*) > 1
            LIMIT 1
            """
        )
    ).fetchone()
    if duplicate is not None:
        raise RuntimeError(
            "Cannot add uq_notebook_message_notebook_id_seq; duplicate rows found "
            f"for notebook_id={duplicate[0]} seq={duplicate[1]} count={duplicate[2]}"
        )

    op.create_unique_constraint(
        "uq_notebook_message_notebook_id_seq",
        "notebook_message",
        ["notebook_id", "seq"],
    )
    op.create_index(
        "ix_notebook_message_notebook_id_seq",
        "notebook_message",
        ["notebook_id", "seq"],
        unique=False,
    )

    op.create_check_constraint(
        "ck_notebook_document_status_valid",
        "notebook_document",
        "status IN ('pending', 'uploaded', 'processing', 'indexed', 'failed')",
    )
    op.create_check_constraint(
        "ck_user_role_valid",
        "user",
        "role IN ('user', 'admin')",
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_notebook_document_notebook_user_created_at
        ON notebook_document (notebook_id, user_id, created_at DESC)
        """
    )
    op.create_index(
        "ix_notebook_document_notebook_user_filename",
        "notebook_document",
        ["notebook_id", "user_id", "filename"],
        unique=False,
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_notebook_report_notebook_user_created_at
        ON notebook_report (notebook_id, user_id, created_at DESC)
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notebook_report_notebook_user_created_at", table_name="notebook_report"
    )
    op.drop_index(
        "ix_notebook_document_notebook_user_filename", table_name="notebook_document"
    )
    op.drop_index(
        "ix_notebook_document_notebook_user_created_at", table_name="notebook_document"
    )

    op.drop_constraint("ck_user_role_valid", "user", type_="check")
    op.drop_constraint(
        "ck_notebook_document_status_valid", "notebook_document", type_="check"
    )

    op.drop_index("ix_notebook_message_notebook_id_seq", table_name="notebook_message")
    op.drop_constraint(
        "uq_notebook_message_notebook_id_seq", "notebook_message", type_="unique"
    )
