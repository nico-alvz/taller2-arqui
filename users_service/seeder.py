from faker import Faker
from sqlalchemy.orm import Session
from passlib.hash import bcrypt
import os
import json
import pika

from .db import SessionLocal, Base, engine
from . import models

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
            publish_created(u)
        return users
    finally:
        db.close()

if __name__ == "__main__":
    created = seed()
    for u in created:
        print({"id": u.id, "email": u.email, "full_name": u.full_name})
