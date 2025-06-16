from sqlalchemy import Column, String, DateTime
from sqlalchemy.sql import func

from auth_service.users_db import Base

class BlacklistedToken(Base):
    __tablename__ = 'blacklisted_tokens'
    __table_args__ = {'schema': 'public'}

    token = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
