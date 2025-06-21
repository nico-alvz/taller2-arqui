import enum
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Enum, Boolean
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class RoleEnum(str, enum.Enum):
    admin = "Administrador"
    client = "Cliente"

class User(Base):
    __tablename__ = 'users'

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    first_name = Column(String(50), nullable=False)
    last_name  = Column(String(50), nullable=False)
    email      = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    role = Column(Enum(RoleEnum), default=RoleEnum.client, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)