import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

USERS_DB_URL = os.getenv('USERS_DB_URL', 'mysql+pymysql://root:example@localhost/streamflow_users')

connect_args = {}
pool_args = {}
if USERS_DB_URL.startswith('sqlite'):
    from sqlalchemy.pool import StaticPool
    connect_args = {"check_same_thread": False}
    pool_args = {"poolclass": StaticPool}

engine = create_engine(USERS_DB_URL, connect_args=connect_args, **pool_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
