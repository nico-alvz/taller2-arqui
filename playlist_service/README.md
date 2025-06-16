# Microservicio de Playlist

## Requisitos
- Python 3.11
- RabbitMQ
- Base de datos SQL

## Variables de entorno
- `PLAYLIST_DB_URL`
- `AMQP_URL`
- `JWT_SECRET`
- `ENV_PATH` (ruta a `.env` opcional)

## Migraciones
```bash
alembic upgrade head