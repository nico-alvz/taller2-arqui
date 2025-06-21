FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instala Caddy
RUN apt-get update \
 && apt-get install -y caddy \
 && rm -rf /var/lib/apt/lists/*

# Copia tu código y configuración de Caddy
COPY . .
COPY Caddyfile /etc/caddy/Caddyfile

# Expone el puerto 80 para HTTP/1.1 (health) + h2c (gRPC)
EXPOSE 80

# Arranca tu gRPC y Caddy
CMD sh -c "\
    export GRPC_PORT=50052 && \
    python main.py & \
    caddy run --config /etc/caddy/Caddyfile --adapter caddyfile\
"
