# db.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import ArgumentError

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set!")

try:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
except ArgumentError as e:
    raise RuntimeError(f"Invalid DATABASE_URL: {e}")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
