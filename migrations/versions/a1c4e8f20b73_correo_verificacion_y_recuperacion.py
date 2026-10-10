"""correo en usuarios; códigos de verificación con propósito (verificar correo / recuperar clave)

Revision ID: a1c4e8f20b73
Revises: 77b785c5bc9b
Create Date: 2026-10-10 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1c4e8f20b73'
down_revision = '77b785c5bc9b'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('email_verified_at', sa.DateTime(), nullable=True))
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)

    # Los códigos viejos eran de celular y nunca llegaron a nadie: se descartan junto con la tabla anterior.
    op.drop_table('phone_verifications')
    op.create_table('verification_codes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('purpose', sa.String(length=20), nullable=False),
        sa.Column('code_hash', sa.String(length=64), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('verification_codes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_verification_codes_user_id'), ['user_id'], unique=False)


def downgrade():
    with op.batch_alter_table('verification_codes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_verification_codes_user_id'))
    op.drop_table('verification_codes')
    op.create_table('phone_verifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('code_hash', sa.String(length=64), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('phone_verifications', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_phone_verifications_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_email'))
        batch_op.drop_column('email_verified_at')
        batch_op.drop_column('email')
