"""convert legacy naive timestamps to timezone-aware

Revision ID: 20260601_0010
Revises: 20260601_0009
Create Date: 2026-06-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260601_0010"
down_revision: str | Sequence[str] | None = "20260601_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "user",
        "created_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "user",
        "updated_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="updated_at AT TIME ZONE 'UTC'",
    )

    op.alter_column(
        "pending_registration",
        "created_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "pending_registration",
        "updated_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="updated_at AT TIME ZONE 'UTC'",
    )

    op.alter_column(
        "refresh_token",
        "created_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )

    op.alter_column(
        "notebook",
        "created_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "notebook",
        "updated_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="updated_at AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    op.alter_column("notebook", "updated_at", type_=sa.DateTime(timezone=False), postgresql_using="updated_at AT TIME ZONE 'UTC'")
    op.alter_column("notebook", "created_at", type_=sa.DateTime(timezone=False), postgresql_using="created_at AT TIME ZONE 'UTC'")

    op.alter_column("refresh_token", "created_at", type_=sa.DateTime(timezone=False), postgresql_using="created_at AT TIME ZONE 'UTC'")

    op.alter_column(
        "pending_registration",
        "updated_at",
        type_=sa.DateTime(timezone=False),
        postgresql_using="updated_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "pending_registration",
        "created_at",
        type_=sa.DateTime(timezone=False),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )

    op.alter_column("user", "updated_at", type_=sa.DateTime(timezone=False), postgresql_using="updated_at AT TIME ZONE 'UTC'")
    op.alter_column("user", "created_at", type_=sa.DateTime(timezone=False), postgresql_using="created_at AT TIME ZONE 'UTC'")
