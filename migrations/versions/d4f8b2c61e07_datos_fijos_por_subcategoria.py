"""categories.fixed_attrs: datos que decide la subcategoría (Toros = macho, Yeguas = yegua…)

Revision ID: d4f8b2c61e07
Revises: c3e7a1b94d52
Create Date: 2026-10-19 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4f8b2c61e07'
down_revision = 'c3e7a1b94d52'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('categories', schema=None) as batch_op:
        batch_op.add_column(sa.Column('fixed_attrs', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('categories', schema=None) as batch_op:
        batch_op.drop_column('fixed_attrs')
