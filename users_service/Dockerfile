FROM python:3.11-slim
WORKDIR /app

# 1) Instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2) Copiar todo el código
COPY . .

# 3) Generar stubs y parchear el import
RUN mkdir -p gen \
    && touch gen/__init__.py \
    && python -m grpc_tools.protoc \
         -I./proto \
         --python_out=./gen \
         --grpc_python_out=./gen \
         proto/users.proto \
    && sed -i \
         's|^import users_pb2 as|from . import users_pb2 as|' \
         gen/users_pb2_grpc.py

# 4) Exponer puerto y arrancar
EXPOSE 50051 50052
CMD ["python", "main.py"]
