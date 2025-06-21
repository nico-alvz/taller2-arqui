FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instala Caddy
RUN apt-get update && apt-get install -y caddy

COPY . .
# Caddyfile en /etc/caddy/Caddyfile
COPY Caddyfile /etc/caddy/Caddyfile

# Primero expone el proxy (que sirve health y gRPC)
EXPOSE 80

CMD sh -c "\
    export GRPC_PORT=50052 && \
    python main.py & \
    caddy run --config /etc/caddy/Caddyfile --adapter caddyfile\
"
