import os
import sys

# Use in-memory SQLite for tests
os.environ['USERS_DB_URL'] = 'sqlite:///:memory:'

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from users_service import seeder
from users_service.db import Base, engine

Base.metadata.create_all(bind=engine)

def test_seed_creates_users():
    users = seeder.seed(2)
    assert len(users) == 2
    assert all(user.id for user in users)
