import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
dotenv_path = os.getenv("ENV_PATH", ".env")
load_dotenv(dotenv_path)

# Fetch database URL from USERS_DB_URL
us_db_url = os.getenv("USERS_DB_URL")
if not us_db_url:
    raise RuntimeError("Environment variable USERS_DB_URL must be set in .env")

# Create the SQLAlchemy engine and session factory
engine = create_engine(
    us_db_url,
    poolclass=QueuePool,
    pool_size=3,        # 3 conexiones persistentes
    max_overflow=2,     # +2 conexiones “extra” de forma temporal
    pool_pre_ping=True, # revivir conexiones muertas
    pool_recycle=3600,  # reciclar cada hora
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)