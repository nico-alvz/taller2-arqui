"""create playlists tables"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import CHAR

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'playlists',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('user_id', CHAR(36), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    op.create_table(
        'playlist_videos',
        sa.Column('playlist_id', sa.Integer, sa.ForeignKey('playlists.id'), primary_key=True),
        sa.Column('video_id', CHAR(24), primary_key=True),
        sa.Column('added_at', sa.DateTime(), server_default=sa.text('now()')),
    )

def downgrade():
    op.drop_table('playlist_videos')
    op.drop_table('playlists')
