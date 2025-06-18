# Usamos Python para el app y añadimos nginx para el health-proxy
FROM python:3.10-slim

# Instala nginx
RUN apt-get update && apt-get install -y nginx && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instala dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia el código del servicio y la configuración de nginx
COPY . .
COPY nginx.conf /etc/nginx/nginx.conf

# Exponemos el puerto público que Render checkea
EXPOSE 50051

# Arranca el servidor gRPC en GRPC_PORT=50052 y nginx en foreground
CMD sh -c "\
    export GRPC_PORT=50052 && \
    python main.py & \
    nginx -g 'daemon off;'\
"
