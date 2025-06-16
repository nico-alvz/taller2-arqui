import os
import json
import uuid
from faker import Faker
from db import SessionLocal
from models import Base, User, RoleEnum
import pika

dotenv_path = os.getenv("ENV_PATH", ".env")
# carga .env si usas

Base.metadata.create_all(bind=None)

fake = Faker()
db = SessionLocal()

# Crear admin fijo
admin = User(
    first_name="Admin", last_name="User", email="admin@example.com",
    password_hash=fake.password(), role=RoleEnum.admin)
db.add(admin)

events = []
for _ in range(150):
    u = User(
        first_name=fake.first_name(), last_name=fake.last_name(),
        email=fake.unique.email(),
        password_hash=fake.password(), role=RoleEnum.client)
    db.add(u)
    events.append({"id": str(u.id), "email": u.email,
                   "first_name": u.first_name, "last_name": u.last_name})

db.commit()
# Publicar eventos
params = pika.URLParameters(os.getenv("AMQP_URL"))
conn = pika.BlockingConnection(params)
ch = conn.channel()
ch.exchange_declare(exchange="users", exchange_type="fanout")
for ev in events:
    ch.basic_publish(exchange="users", routing_key="", body=json.dumps({"type":"created", **ev}))
conn.close()