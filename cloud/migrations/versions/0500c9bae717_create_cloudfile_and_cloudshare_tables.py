"""Create CloudFile and CloudShare tables

Revision ID: 0500c9bae717
Revises: 
Create Date: 2026-09-26 17:38:56.024131

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0500c9bae717'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Создаём таблицы cloud_file и cloud_share."""

    # === Таблица cloud_file ===
    op.create_table(
        'cloud_file',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('is_folder', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('stored_name', sa.String(length=255), nullable=True),
        sa.Column('size', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('mime_type', sa.String(length=120), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_trashed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('trashed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['parent_id'], ['cloud_file.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stored_name'),
    )
    with op.batch_alter_table('cloud_file', schema=None) as batch_op:
        batch_op.create_index('ix_cloud_file_owner_id', ['owner_id'], unique=False)
        batch_op.create_index('ix_cloud_file_parent_id', ['parent_id'], unique=False)
        batch_op.create_index('ix_cloud_file_is_folder', ['is_folder'], unique=False)
        batch_op.create_index('ix_cloud_file_created_at', ['created_at'], unique=False)
        batch_op.create_index('ix_cloud_file_is_trashed', ['is_trashed'], unique=False)

    # === Таблица cloud_share ===
    op.create_table(
        'cloud_share',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('file_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('created_by_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('password_hash', sa.String(length=256), nullable=True),
        sa.Column('download_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_downloads', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['file_id'], ['cloud_file.id'], ),
        sa.ForeignKeyConstraint(['created_by_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token'),
    )
    with op.batch_alter_table('cloud_share', schema=None) as batch_op:
        batch_op.create_index('ix_cloud_share_file_id', ['file_id'], unique=False)
        batch_op.create_index('ix_cloud_share_token', ['token'], unique=False)


def downgrade():
    """Удаляем таблицы в обратном порядке."""
    op.drop_table('cloud_share')
    op.drop_table('cloud_file')
