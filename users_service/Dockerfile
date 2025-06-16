FROM python:3.11-slim
WORKDIR /app

# Instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Generar stubs de gRPC dentro de gen/
RUN mkdir -p gen && touch gen/__init__.py && \
    python -m grpc_tools.protoc -I./proto --python_out=./gen --grpc_python_out=./gen proto/users.proto

EXPOSE 50051

CMD ["python", "main.py"]