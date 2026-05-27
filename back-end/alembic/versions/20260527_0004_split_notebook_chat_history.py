"""split notebook chat history into message rows

Revision ID: 20260527_0004
Revises: 20260527_0003
Create Date: 2026-05-27 00:04:00.000000
"""

import json
from collections.abc import Sequence
from datetime import datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260527_0004"
down_revision: str | Sequence[str] | None = "20260527_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notebook_message",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notebook_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column(
            "message",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["notebook_id"], ["notebook.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notebook_message_notebook_id", "notebook_message", ["notebook_id"], unique=False)
    op.create_index("ix_notebook_message_seq", "notebook_message", ["seq"], unique=False)

    bind = op.get_bind()
    notebook_rows = bind.execute(
        sa.text("SELECT id, chat_history, created_at, updated_at FROM notebook")
    ).fetchall()
    for row in notebook_rows:
        chat_history = row.chat_history or []
        if not isinstance(chat_history, list):
            continue
        created_at = row.updated_at or row.created_at or datetime.utcnow()
        for idx, message in enumerate(chat_history, start=1):
            bind.execute(
                sa.text(
                    """
                    INSERT INTO notebook_message (id, notebook_id, seq, message, created_at)
                    VALUES (:id, :notebook_id, :seq, :message, :created_at)
                    """
                ),
                {
                    "id": str(uuid4()),
                    "notebook_id": str(row.id),
                    "seq": idx,
                    "message": json.dumps(message),
                    "created_at": created_at,
                },
            )

    op.drop_column("notebook", "chat_history")


def downgrade() -> None:
    default = sa.text("'[]'::jsonb") if op.get_bind().dialect.name == "postgresql" else sa.text("'[]'")
    op.add_column(
        "notebook",
        sa.Column(
            "chat_history",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            server_default=default,
            nullable=False,
        ),
    )

    bind = op.get_bind()
    notebook_ids = [row.id for row in bind.execute(sa.text("SELECT id FROM notebook")).fetchall()]
    for notebook_id in notebook_ids:
        rows = bind.execute(
            sa.text(
                """
                SELECT message
                FROM notebook_message
                WHERE notebook_id = :notebook_id
                ORDER BY seq ASC
                """
            ),
            {"notebook_id": str(notebook_id)},
        ).fetchall()
        bind.execute(
            sa.text("UPDATE notebook SET chat_history = :chat_history WHERE id = :notebook_id"),
            {
                "chat_history": json.dumps([row.message for row in rows]),
                "notebook_id": str(notebook_id),
            },
        )

    op.alter_column("notebook", "chat_history", server_default=None)
    op.drop_index("ix_notebook_message_seq", table_name="notebook_message")
    op.drop_index("ix_notebook_message_notebook_id", table_name="notebook_message")
    op.drop_table("notebook_message")
