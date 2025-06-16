import os
import json
import uuid
from concurrent import futures
from datetime import datetime

import pika
import jwt
from fastapi import HTTPException
from sqlalchemy.orm import Session
import grpc
from grpc import ServicerContext
from google.protobuf.timestamp_pb2 import Timestamp

from db import SessionLocal, engine
from models import Base, User, RoleEnum
from gen import users_pb2, users_pb2_grpc
from dotenv import load_dotenv
from passlib.hash import bcrypt

# Cargar .env
dotenv_path = os.getenv("ENV_PATH", ".env")
load_dotenv(dotenv_path)

# Inicializar DB y RabbitMQ params
Base.metadata.create_all(bind=engine)
AMQP_URL = os.getenv("AMQP_URL")
JWT_SECRET = os.getenv("JWT_SECRET", "secret")

# Publisher helper
def publish_event(event_type, payload: dict):
    params = pika.URLParameters(AMQP_URL)
    conn = pika.BlockingConnection(params)
    ch = conn.channel()
    ch.exchange_declare(exchange="users", exchange_type="fanout")
    message = json.dumps({"type": event_type, **payload})
    ch.basic_publish(exchange="users", routing_key="", body=message)
    conn.close()

# JWT utils
def decode_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.PyJWTError:
        raise HTTPException(401, "Token inválido")

# Interceptor para auth
def auth_interceptor(method, request, context: ServicerContext, next_call):
    # Métodos públicos: CreateUser con role=Cliente
    if method.__name__ == 'CreateUser':
        token = dict(context.invocation_metadata()).get('authorization', '')
        if token:
            data = decode_token(token.split()[1])
            # si crea admin, requiere admin
            if request.role == RoleEnum.admin.value and data.get('role') != RoleEnum.admin.value:
                context.abort(403, "Solo admin puede crear administradores")
        else:
            if request.role == RoleEnum.admin.value:
                context.abort(401, "Token requerido para crear admin")
        return next_call(request, context)

    # Para otros, extraer y validar token
    token = dict(context.invocation_metadata()).get('authorization', '')
    if not token:
        context.abort(401, "Token requerido")
    data = decode_token(token.split()[1])
    context.user = data
    return next_call(request, context)

# Servicio gRPC\class UserService(users_pb2_grpc.UserServiceServicer):

    def CreateUser(self, req, ctx):
        db: Session = SessionLocal()
        if req.password != req.password_confirmation:
            ctx.abort(400, "Las contraseñas no coinciden")
        if db.query(User).filter_by(email=req.email).first():
            ctx.abort(400, "Email ya registrado")
        pwd_hash = bcrypt.hash(req.password)
        user = User(first_name=req.first_name, last_name=req.last_name,
                    email=req.email, password_hash=pwd_hash,
                    role=RoleEnum(req.role))
        db.add(user); db.commit(); db.refresh(user)
        publish_event('created', {"id": str(user.id), "email": user.email,
                                  "first_name": user.first_name,
                                  "last_name": user.last_name})
        ts = Timestamp(); ts.FromDatetime(user.created_at)
        return users_pb2.UserResponse(user=users_pb2.User(
            id=str(user.id), first_name=user.first_name, last_name=user.last_name,
            email=user.email, role=user.role.value, created_at=ts))

    def GetUserById(self, req, ctx):
        db: Session = SessionLocal()
        u = db.query(User).get(uuid.UUID(req.id))
        if not u or u.deleted_at:
            ctx.abort(404, "Usuario no encontrado")
        user_ctx = ctx.user
        if user_ctx['role'] != RoleEnum.admin.value and user_ctx['sub'] != req.id:
            ctx.abort(403, "No autorizado")
        ts = Timestamp(); ts.FromDatetime(u.created_at)
        return users_pb2.UserResponse(user=users_pb2.User(
            id=req.id, first_name=u.first_name, last_name=u.last_name,
            email=u.email, role=u.role.value, created_at=ts))

    def UpdateUser(self, req, ctx):
        db: Session = SessionLocal()
        u = db.query(User).get(uuid.UUID(req.id))
        if not u or u.deleted_at:
            ctx.abort(404, "Usuario no encontrado")
        user_ctx = ctx.user
        if user_ctx['role'] != RoleEnum.admin.value and user_ctx['sub'] != req.id:
            ctx.abort(403, "No autorizado")
        u.first_name = req.first_name; u.last_name = req.last_name; u.email = req.email
        db.commit(); db.refresh(u)
        publish_event('updated', {"id": str(u.id), "email": u.email,
                                  "first_name": u.first_name,
                                  "last_name": u.last_name})
        ts = Timestamp(); ts.FromDatetime(u.created_at)
        return users_pb2.UserResponse(user=users_pb2.User(
            id=req.id, first_name=u.first_name, last_name=u.last_name,
            email=u.email, role=u.role.value, created_at=ts))

    def DeleteUser(self, req, ctx):
        db: Session = SessionLocal()
        u = db.query(User).get(uuid.UUID(req.id))
        if not u or u.deleted_at:
            ctx.abort(404, "Usuario no encontrado")
        if ctx.user['role'] != RoleEnum.admin.value:
            ctx.abort(403, "Solo admin puede eliminar")
        u.deleted_at = datetime.utcnow()
        db.commit()
        publish_event('deleted', {"id": req.id})
        return users_pb2.Empty()

        def ListUsers(self, req, ctx):
        if ctx.user['role'] != RoleEnum.admin.value:
            ctx.abort(403, "Solo admin puede listar usuarios")
        db: Session = SessionLocal()
        q = db.query(User).filter(User.deleted_at.is_(None))
        # Email
        if req.email:
            q = q.filter(User.email.ilike(f"%{req.email}%"))
        # Nombre
        if req.first_name:
            q = q.filter(User.first_name.ilike(f"%{req.first_name}%"))
        # Apellido (AND con nombre si se mandan ambos)
        if req.last_name:
            q = q.filter(User.last_name.ilike(f"%{req.last_name}%"))
        result = []
        for u in q.all():
            ts = Timestamp(); ts.FromDatetime(u.created_at)
            result.append(users_pb2.User(
                id=str(u.id), first_name=u.first_name, last_name=u.last_name,
                email=u.email, role=u.role.value, created_at=ts))
        return users_pb2.ListUsersResponse(users=result)

# Servidor gRPC
server = grpc.server(futures.ThreadPoolExecutor(max_workers=10), interceptors=[auth_interceptor])
users_pb2_grpc.add_UserServiceServicer_to_server(UserService(), server)
server.add_insecure_port('[::]:50051')

if __name__ == '__main__':
    print("Starting gRPC server on port 50051...")
    server.start()
    server.wait_for_termination()