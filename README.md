# StreamFlow Microservices Skeleton

This repository contains a minimal scaffold for the services described in the workshop documents.

## Services
- **AuthService**: FastAPI service for authentication on port 8000.
- **UsersService**: FastAPI CRUD for users on port 8001.
- **PlaylistService**: FastAPI service for playlists on port 8002.
- **EmailService**: Node.js service using Express and nodemailer on port 8003.
- **Contracts**: gRPC proto definitions and RabbitMQ exchanges in `contracts/`.
- **APIGateway**: FastAPI proxy routing requests to services on port 8004.
- **Mocks**: Video and Billing services with dummy endpoints.

Databases (Postgres and MariaDB) and RabbitMQ are included in `docker-compose.yml`.

## Quick start
```bash
docker compose up --build
```
Services expose `/healthz` endpoints for checks.

## Seeding example users
Run the users service seeder to populate the database with fake data:
```bash
cd users_service
python seeder.py
```
An example output is provided in `sample_seed_output.json`.

## Running AuthService migrations
Alembic is configured for AuthService. To create the tokens table locally:

```bash
cd auth_service
alembic upgrade head
```

