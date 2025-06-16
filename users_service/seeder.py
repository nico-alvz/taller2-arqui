from faker import Faker
from sqlalchemy.orm import Session
from passlib.hash import bcrypt
import os
import json
import pika

from users_service.db import SessionLocal, Base, engine
from users_service import models

fake = Faker()

Base.metadata.create_all(bind=engine)

AMQP_URL = os.getenv("AMQP_URL")

def publish_created(user):
    if not AMQP_URL:
        return
    params = pika.URLParameters(AMQP_URL)
    conn = pika.BlockingConnection(params)
    ch = conn.channel()
    ch.exchange_declare(exchange="users", exchange_type="fanout")
    ch.basic_publish(
        exchange="users",
        routing_key="",
        body=json.dumps({"id": user.id, "email": user.email, "full_name": user.full_name}),
    )
    conn.close()


def seed(n: int = 150):
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
            publish_created(u)
        return users
    finally:
        db.close()

if __name__ == "__main__":
    import sys, pathlib
    if __package__ is None:
        sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    created = seed(n)
    for u in created:
        print({"id": u.id, "email": u.email, "full_name": u.full_name})
