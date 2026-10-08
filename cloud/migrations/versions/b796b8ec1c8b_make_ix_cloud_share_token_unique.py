"""Make ix_cloud_share_token unique

Revision ID: b796b8ec1c8b
Revises: 0500c9bae717
Create Date: 2026-09-26 18:32:48.694721

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b796b8ec1c8b'
down_revision = '0500c9bae717'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('cloud_share', schema=None) as batch_op:
        batch_op.drop_index('ix_cloud_share_token')
        batch_op.create_index('ix_cloud_share_token', ['token'], unique=True)


def downgrade():
    with op.batch_alter_table('cloud_share', schema=None) as batch_op:
        batch_op.drop_index('ix_cloud_share_token')
        batch_op.create_index('ix_cloud_share_token', ['token'], unique=False)