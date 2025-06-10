import os, sys
from fastapi.testclient import TestClient

os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['USERS_DB_URL'] = 'sqlite:///:memory:'
os.environ['JWT_SECRET'] = 'secret'

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from auth_service.db import Base as TokenBase, engine as token_engine
from auth_service.users_db import Base as UsersBase, engine as users_engine, SessionLocal as UsersSession
from auth_service.users_models import User
from passlib.hash import bcrypt
from auth_service.main import app

TokenBase.metadata.create_all(bind=token_engine)
UsersBase.metadata.create_all(bind=users_engine)

session = UsersSession()
session.add(User(email='user@example.com', password_hash=bcrypt.hash('password')))
session.commit()
session.close()

client = TestClient(app)

def test_login_and_logout():
    res = client.post('/auth/login', json={'email': 'user@example.com', 'password': 'password'})
    assert res.status_code == 200
    token = res.json()['access_token']
    out = client.post('/auth/logout', json={'token': token})
    assert out.status_code == 200
