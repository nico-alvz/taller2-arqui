import os
import uuid
from faker import Faker
from db import SessionLocal
from models import Base, Playlist
import pika

load_env = lambda: None  # usar dotenv si es necesario
Base.metadata.create_all(bind=SessionLocal().bind)

fake = Faker()
db = SessionLocal()
owner_id = uuid.UUID(os.getenv('SEED_OWNER_ID', uuid.uuid4().hex))

# Crear 20 playlists
playlists = []
for _ in range(20):
    p = Playlist(name=fake.sentence(nb_words=3), description=fake.text(max_nb_chars=100), owner_id=owner_id)
    db.add(p)
    playlists.append(p)

db.commit()

# Publicar eventos
conn = pika.BlockingConnection(pika.URLParameters(os.getenv('AMQP_URL')))
ch = conn.channel()
ch.exchange_declare(exchange='playlists', exchange_type='fanout')
for p in playlists:
    ch.basic_publish(exchange='playlists', routing_key='', body=json.dumps({'event':'playlist.created','id':str(p.id),'owner_id':str(owner_id)}))
conn.close()