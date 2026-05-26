"""create auth tables

Revision ID: 20260526_0001
Revises:
Create Date: 2026-05-26 00:01:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260526_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_email", "user", ["email"], unique=True)

    op.create_table(
        "pendingregistration",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("hashed_otp", sa.String(), nullable=False),
        sa.Column("otp_attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pendingregistration_email", "pendingregistration", ["email"], unique=True)

    op.create_table(
        "refreshtoken",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_token_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["replaced_by_token_id"], ["refreshtoken.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_refreshtoken_family_id", "refreshtoken", ["family_id"], unique=False)
    op.create_index("ix_refreshtoken_token_hash", "refreshtoken", ["token_hash"], unique=True)
    op.create_index("ix_refreshtoken_user_id", "refreshtoken", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_refreshtoken_user_id", table_name="refreshtoken")
    op.drop_index("ix_refreshtoken_token_hash", table_name="refreshtoken")
    op.drop_index("ix_refreshtoken_family_id", table_name="refreshtoken")
    op.drop_table("refreshtoken")
    op.drop_index("ix_pendingregistration_email", table_name="pendingregistration")
    op.drop_table("pendingregistration")
    op.drop_index("ix_user_email", table_name="user")
    op.drop_table("user")
