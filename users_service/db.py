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
engine = create_engine(us_db_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)