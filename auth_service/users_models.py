# users_models.py

import enum
import uuid
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import ENUM as PGEnum

from auth_service.users_db import Base

class RoleEnum(str, enum.Enum):
    free = 'free'
    premium = 'premium'
    admin = 'admin'

class User(Base):
    __tablename__ = 'users'
    __table_args__ = {'schema': 'auth'}

    id = Column(
        CHAR(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100))

    role = Column(
        PGEnum(
            RoleEnum,
            name="roleenum",    # nombre del ENUM en la BD
            schema="auth",      # esquema donde se crea el tipo
            create_type=True    # SQLAlchemy genera CREATE TYPE
        ),
        nullable=False,
        default=RoleEnum.free
    )

    created_at = Column(
        DateTime,
        server_default=func.now()
    )
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )
