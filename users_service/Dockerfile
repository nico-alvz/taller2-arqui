# Usa Python + nginx
FROM python:3.10-slim

# 1) Instala nginx y elimina cualquier config por defecto
RUN apt-get update \
 && apt-get install -y nginx \
 && rm -rf /var/lib/apt/lists/* \
 && rm -f /etc/nginx/conf.d/default.conf /etc/nginx/sites-enabled/*

WORKDIR /app

# 2) Instala deps Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3) Copia tu código y la config personalizada de nginx
COPY . .
COPY nginx.conf /etc/nginx/nginx.conf

# 4) Asegúrate de exponer el puerto que Render escanea (10000)
EXPOSE 10000

# 5) Arranca gRPC en GRPC_PORT=50052 y nginx en primer plano
CMD sh -c "\
    export GRPC_PORT=50052 && \
    python main.py & \
    nginx -g 'daemon off;' \
"
