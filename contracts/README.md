# Service Contracts

This folder contains gRPC protocol definitions and a summary of RabbitMQ exchanges used for asynchronous communication.

## gRPC Protos
- `auth.proto` – authentication RPCs
- `users.proto` – user management RPCs
- `playlist.proto` – playlist CRUD RPCs

## RabbitMQ Exchanges
- `user.events` – publishes `user.created` whenever a new user is registered.
- `billing.events` – sends `invoice.paid` events from BillingService.
- `email.events` – EmailService publishes `email.sent` for monitoring.
