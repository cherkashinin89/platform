"""W3: Photo.file_id -> cloud_file.id

Revision ID: b3fce6fbe4b6
Revises: bec349bf7b84
Create Date: 2026-10-07 00:57:34.299651

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b3fce6fbe4b6'
down_revision = 'bec349bf7b84'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('photo', schema=None) as batch_op:
        batch_op.drop_constraint('photo_file_id_fkey', type_='foreignkey')
        batch_op.create_foreign_key(
            'photo_file_id_fkey', 'cloud_file',
            ['file_id'], ['id'], ondelete='CASCADE'
        )

    # ### end Alembic commands ###


def downgrade():
    with op.batch_alter_table('photo', schema=None) as batch_op:
        batch_op.drop_constraint('photo_file_id_fkey', type_='foreignkey')
        batch_op.create_foreign_key(
            'photo_file_id_fkey', 'uploaded_file',
            ['file_id'], ['id']
        )

    # ### end Alembic commands ###
