from faker import Faker
from sqlalchemy.orm import Session
from passlib.hash import bcrypt

from .db import SessionLocal, Base, engine
from . import models

fake = Faker()

Base.metadata.create_all(bind=engine)

def seed(n: int = 5):
    db: Session = SessionLocal()
    users = []
    try:
        for _ in range(n):
            u = models.User(
                email=fake.unique.email(),
                password_hash=bcrypt.hash("password"),
                full_name=fake.name(),
            )
            db.add(u)
            users.append(u)
        db.commit()
        for u in users:
            db.refresh(u)
        return users
    finally:
        db.close()

if __name__ == "__main__":
    created = seed()
    for u in created:
        print({"id": u.id, "email": u.email, "full_name": u.full_name})
