"""attribute_defs: preguntas condicionales (show_if_key / show_if_values)

Revision ID: c3e7a1b94d52
Revises: b2d5f9a31c84
Create Date: 2026-10-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3e7a1b94d52'
down_revision = 'b2d5f9a31c84'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('attribute_defs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('show_if_key', sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column('show_if_values', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('attribute_defs', schema=None) as batch_op:
        batch_op.drop_column('show_if_values')
        batch_op.drop_column('show_if_key')
