from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import CHAR
from sqlalchemy.sql import func
from playlist_service.db import Base

class Playlist(Base):
    __tablename__ = 'playlists'
    id = Column(Integer, primary_key=True)
    user_id = Column(CHAR(36), nullable=False)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class PlaylistVideo(Base):
    __tablename__ = 'playlist_videos'
    playlist_id = Column(Integer, ForeignKey('playlists.id'), primary_key=True)
    video_id = Column(CHAR(24), primary_key=True)
    added_at = Column(DateTime, server_default=func.now())
