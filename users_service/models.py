from sqlalchemy import Column, String, Enum, DateTime
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.sql import func
import enum
import uuid

from .db import Base

class RoleEnum(str, enum.Enum):
    free = 'free'
    premium = 'premium'
    admin = 'admin'

class User(Base):
    __tablename__ = 'users'

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100))
    role = Column(Enum(RoleEnum), nullable=False, default=RoleEnum.free)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
