"""add indexes for todos

Revision ID: b123456789ab
Revises: a0790c76a129
Create Date: 2026-10-07 04:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b123456789ab'
down_revision = 'a0790c76a129'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_todos_user_id_created_at', 'todos', ['user_id', 'created_at'], unique=False)


def downgrade():
    op.drop_index('ix_todos_user_id_created_at', table_name='todos')
