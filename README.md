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

Run the users service seeder to populate the database with fake data. By default
it creates 150 users. If `AMQP_URL` is set it will publish `user.created` events
to RabbitMQ. You can optionally pass the desired amount as an argument:
```bash
cd users_service
python seeder.py        # creates 150 users
python seeder.py 200    # create 200 users instead
=======
Run the users service seeder to populate the database with fake data. If `AMQP_URL`
is set it will publish `user.created` events to RabbitMQ:
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

## Running UsersService migrations
To initialize the users table locally:

```bash
cd users_service
alembic upgrade head
```

## Running PlaylistService migrations
Initialize the playlist tables locally:

```bash
cd playlist_service
alembic upgrade head
```


## Generating Postman collection
With the gateway running you can export its OpenAPI spec and import to Postman:

```bash
curl http://localhost:8004/openapi.json -o gateway_openapi.json
```

## Listening to invoice.paid events
EmailService consumes `billing.events` from RabbitMQ. Ensure `AMQP_URL` is set
in your environment (see `.env.example`) so that invoices published by the
billing mock trigger emails.


## Release
Create a tag when all phases are complete:

```bash
git tag v1.0
```

Diagrams are available in the `docs/` folder as PlantUML files.

