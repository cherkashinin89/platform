"""add user.mail_quota_bytes

Revision ID: 5a8e2fd60c6b
Revises: 9f246cb32d6e
Create Date: 2026-10-12 18:51:03.223050

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5a8e2fd60c6b'
down_revision = '9f246cb32d6e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('mail_quota_bytes', sa.BigInteger(), nullable=False, server_default='1073741824'))


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('mail_quota_bytes')