import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Playlist(Base):
    __tablename__ = 'playlists'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    owner_id = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    videos = relationship('PlaylistVideo', back_populates='playlist')

class PlaylistVideo(Base):
    __tablename__ = 'playlist_videos'
    playlist_id = Column(UUID(as_uuid=True), ForeignKey('playlists.id'), primary_key=True)
    video_id = Column(String(50), primary_key=True)
    added_at = Column(DateTime, default=datetime.utcnow)
    playlist = relationship('Playlist', back_populates='videos')