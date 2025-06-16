# EmailService (Microservicio de Envío de Correos)

Este servicio escucha eventos de facturas y envía correos de forma automática.

## Requisitos
- Node.js 18+
- RabbitMQ
- Servidor SMTP

## Estructura
- `proto/email.proto` – Definición gRPC.
- `index.js` – Servidor gRPC y consumidor RabbitMQ.
- `.env` – Variables de configuración.

## Variables de Entorno
Renombrar `.env.example` a `.env` y ajustar valores:
```bash
AMQP_URL=
GRPC_PORT=
SMTP_HOST=
SMTP_PORT=
SMTP_USER=
SMTP_PASS=