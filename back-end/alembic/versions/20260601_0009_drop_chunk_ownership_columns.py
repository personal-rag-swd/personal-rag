"""drop duplicated chunk ownership columns

Revision ID: 20260601_0009
Revises: 20260601_0008
Create Date: 2026-06-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260601_0009"
down_revision: str | Sequence[str] | None = "20260601_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(
        "ix_notebook_document_chunk_notebook_id", table_name="notebook_document_chunk"
    )
    op.drop_index(
        "ix_notebook_document_chunk_user_id", table_name="notebook_document_chunk"
    )

    op.drop_constraint(
        "notebook_document_chunk_notebook_id_fkey",
        "notebook_document_chunk",
        type_="foreignkey",
    )
    op.drop_constraint(
        "notebook_document_chunk_user_id_fkey",
        "notebook_document_chunk",
        type_="foreignkey",
    )

    op.drop_column("notebook_document_chunk", "notebook_id")
    op.drop_column("notebook_document_chunk", "user_id")


def downgrade() -> None:
    op.add_column(
        "notebook_document_chunk",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "notebook_document_chunk",
        sa.Column("notebook_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.execute(
        """
        UPDATE notebook_document_chunk c
        SET notebook_id = d.notebook_id,
            user_id = d.user_id
        FROM notebook_document d
        WHERE c.document_id = d.id
        """
    )

    op.alter_column("notebook_document_chunk", "notebook_id", nullable=False)
    op.alter_column("notebook_document_chunk", "user_id", nullable=False)

    op.create_foreign_key(
        "notebook_document_chunk_notebook_id_fkey",
        "notebook_document_chunk",
        "notebook",
        ["notebook_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "notebook_document_chunk_user_id_fkey",
        "notebook_document_chunk",
        "user",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_index(
        "ix_notebook_document_chunk_notebook_id",
        "notebook_document_chunk",
        ["notebook_id"],
        unique=False,
    )
    op.create_index(
        "ix_notebook_document_chunk_user_id",
        "notebook_document_chunk",
        ["user_id"],
        unique=False,
    )
