"""users.deleted_at: marca de cuentas eliminadas por su dueño (anonimizadas)

Revision ID: b2d5f9a31c84
Revises: a1c4e8f20b73
Create Date: 2026-10-10 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2d5f9a31c84'
down_revision = 'a1c4e8f20b73'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('deleted_at')
