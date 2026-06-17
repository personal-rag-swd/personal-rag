"""allow_database_notes

Revision ID: 996c25b12e0f
Revises: 20260609_0012
Create Date: 2026-06-17 11:24:48.225020

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '996c25b12e0f'
down_revision: Union[str, Sequence[str], None] = '20260609_0012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('notebook_document', sa.Column('content', sa.Text(), nullable=True))
    op.alter_column('notebook_document', 's3_bucket',
               existing_type=sa.VARCHAR(length=255),
               nullable=True)
    op.alter_column('notebook_document', 's3_key',
               existing_type=sa.VARCHAR(length=1024),
               nullable=True)


def downgrade() -> None:
    op.alter_column('notebook_document', 's3_key',
               existing_type=sa.VARCHAR(length=1024),
               nullable=False)
    op.alter_column('notebook_document', 's3_bucket',
               existing_type=sa.VARCHAR(length=255),
               nullable=False)
    op.drop_column('notebook_document', 'content')
