"""add notebook document rag tables

Revision ID: 20260528_0005
Revises: 20260527_0004
Create Date: 2026-05-28
"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260528_0005"
down_revision = "20260527_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "notebook_document",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notebook_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("s3_bucket", sa.String(length=255), nullable=False),
        sa.Column("s3_key", sa.String(length=1024), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("size", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["notebook_id"], ["notebook.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("s3_key"),
    )
    op.create_index(
        "ix_notebook_document_notebook_id",
        "notebook_document",
        ["notebook_id"],
        unique=False,
    )
    op.create_index(
        "ix_notebook_document_user_id", "notebook_document", ["user_id"], unique=False
    )
    op.create_index(
        "ix_notebook_document_s3_key", "notebook_document", ["s3_key"], unique=False
    )
    op.create_index(
        "ix_notebook_document_status", "notebook_document", ["status"], unique=False
    )

    op.create_table(
        "notebook_document_chunk",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notebook_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"], ["notebook_document.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["notebook_id"], ["notebook.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_notebook_document_chunk_document_id",
        "notebook_document_chunk",
        ["document_id"],
        unique=False,
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
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_notebook_document_chunk_embedding_ivfflat
        ON notebook_document_chunk
        USING ivfflat (embedding vector_cosine_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_notebook_document_chunk_embedding_ivfflat")
    op.drop_index(
        "ix_notebook_document_chunk_user_id", table_name="notebook_document_chunk"
    )
    op.drop_index(
        "ix_notebook_document_chunk_notebook_id", table_name="notebook_document_chunk"
    )
    op.drop_index(
        "ix_notebook_document_chunk_document_id", table_name="notebook_document_chunk"
    )
    op.drop_table("notebook_document_chunk")

    op.drop_index("ix_notebook_document_status", table_name="notebook_document")
    op.drop_index("ix_notebook_document_s3_key", table_name="notebook_document")
    op.drop_index("ix_notebook_document_user_id", table_name="notebook_document")
    op.drop_index("ix_notebook_document_notebook_id", table_name="notebook_document")
    op.drop_table("notebook_document")
