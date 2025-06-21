import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from dotenv import load_dotenv

# Load environment variables
load_dotenv(os.getenv("ENV_PATH", ".env"))

# Fetch database URL from USERS_DB_URL
DATABASE_URL = os.getenv("USERS_DB_URL")
if not DATABASE_URL:
    raise RuntimeError("Environment variable USERS_DB_URL must be set in .env")

# Create the SQLAlchemy engine without pooling
# to avoid exceeding max_user_connections in shared MySQL environments
engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
