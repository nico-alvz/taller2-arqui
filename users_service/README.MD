# Microservicio de Usuarios

## Requisitos
- Docker
- Python 3.11
- RabbitMQ
- Base de datos (PostgreSQL, MySQL, etc.)

## Variables de Entorno
- `USERS_DB_URL` – URL de conexión SQLAlchemy
- `AMQP_URL` – URL de RabbitMQ
- `JWT_SECRET`
- `ENV_PATH` – ruta al archivo .env (opcional)

## Migraciones
```bash
alembic upgrade hea