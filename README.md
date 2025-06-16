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
Services expose `/healthz` endpoints for checks. Each service uses its own
database connection and communicates with RabbitMQ using the `AMQP_URL`
environment variable. AuthService keeps a local copy of users in its database
and stays in sync with UsersService through messages from RabbitMQ.


## Seeding example users

Run the users service seeder to populate the database with fake data. If
`AMQP_URL` is set it will publish `user.created` events to RabbitMQ. Execute it
from the repository root using the module syntax:
```bash
python -m users_service.seeder        # creates 150 users
python -m users_service.seeder 200    # create 200 users instead
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
- **AuthService** stores its own users table together with the token blacklist in
  a single PostgreSQL database. At startup it consumes the `users` exchange from
  RabbitMQ so that new users from **UsersService** are replicated locally.

token blacklist table. Using that token, a client may call
`/auth/usuarios/{id}` to update the password, which modifies the same
PostgreSQL database. Creating users with the seeder inserts rows in
   replicated from RabbitMQ messages published by **UsersService**. Password
   changes hit `/auth/usuarios/{id}` with a valid JWT and update the same
   database.
With the gateway running you can export its OpenAPI spec and import to Postman:

```bash
curl http://localhost:8004/openapi.json -o gateway_openapi.json
```

## Listening to invoice.paid events
EmailService consumes `billing.events` from RabbitMQ. Ensure `AMQP_URL` is set
in your environment (see `.env.example`) so that invoices published by the
billing mock trigger emails.

## How services interact

Every microservice has its own database and connects to the shared RabbitMQ
instance using `AMQP_URL`.

- **UsersService** stores the master users table and publishes `user.created`
  events. Its MariaDB database is independent from the others.
- **AuthService** keeps a replicated users table in PostgreSQL. At startup it
  consumes the `users` exchange from RabbitMQ so new users are inserted locally.
  Login requests validated here store blacklist tokens in the same database.
- **PlaylistService** uses Postgres for playlists and calls the Video mock to
  validate video IDs.
- **EmailService** listens to `billing.events` and sends emails via SMTP.
- **APIGateway** forwards HTTP requests to each service based on path.

For example, a `/auth/login` request travels through the gateway to AuthService.
The service checks the replicated user table, issues a JWT and records it in the
token blacklist table. Creating users with the seeder inserts rows in
UsersService's DB, publishes events through RabbitMQ and AuthService stores a
copy. Invoice events published by the billing mock are consumed by EmailService
to send notifications.

### Request routing narrative

1. Requests to `/auth/*` pass through the gateway to **AuthService**, which
   validates credentials using its own PostgreSQL database. New users are
   replicated from RabbitMQ messages published by **UsersService**.
2. `/users/*` endpoints hit **UsersService** and modify its MariaDB tables.
   Every creation publishes a `user.created` event so other services stay in
   sync.
3. `/playlists/*` routes go to **PlaylistService**, which stores playlists in
   its Postgres database and verifies videos via the mock Video service.
4. Invoices published by the Billing mock land in RabbitMQ. **EmailService**
   consumes these events to send notifications.

All microservices and the API Gateway run as separate containers and share the
RabbitMQ instance defined in `docker-compose.yml`.


## Release
Create a tag when all phases are complete:

```bash
git tag v1.0
```

Diagrams are available in the `docs/` folder as PlantUML files.

