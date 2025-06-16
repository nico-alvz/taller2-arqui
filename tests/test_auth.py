import os, sys
from fastapi.testclient import TestClient

os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
u = User(email='user@example.com', password_hash=bcrypt.hash('password'))
session.add(u)
session.refresh(u)
USER_ID = u.id


def test_change_password():
    res = client.post('/auth/login', json={'email': 'user@example.com', 'password': 'password'})
    token = res.json()['access_token']
    res = client.patch(
        f'/auth/usuarios/{USER_ID}',
        json={
            'current_password': 'password',
            'new_password': 'newpass',
            'confirm_password': 'newpass',
        },
        headers={'Authorization': f'Bearer {token}'},
    )
    assert res.status_code == 200
    assert 'password_hash' not in res.json()
    res = client.post('/auth/login', json={'email': 'user@example.com', 'password': 'newpass'})
    assert res.status_code == 200

os.environ['JWT_SECRET'] = 'secret'

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from auth_service.users_db import Base, engine, SessionLocal
from auth_service.users_models import User
from passlib.hash import bcrypt
from auth_service.main import app

Base.metadata.create_all(bind=engine)

session = SessionLocal()
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
