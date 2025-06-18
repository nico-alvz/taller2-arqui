#!/usr/bin/env python3
import os
import json
import uuid
import logging
from concurrent import futures
from datetime import datetime
from typing import Callable

import pika
import jwt
from fastapi import HTTPException
from sqlalchemy.orm import Session
import grpc
from grpc import ServicerContext, ServerInterceptor
from google.protobuf.timestamp_pb2 import Timestamp
from dotenv import load_dotenv
from passlib.hash import bcrypt

from db import SessionLocal, engine
from models import Base, User, RoleEnum
from gen import users_pb2, users_pb2_grpc

# -----------------------------------------------------
# Logging configuration
# -----------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s:%(lineno)d] %(message)s",
)
logger = logging.getLogger("user_service")

# -----------------------------------------------------
# Load environment variables
# -----------------------------------------------------
load_dotenv(os.getenv("ENV_PATH", ".env"))

# Database & RabbitMQ config
USERS_DB_URL = os.getenv("USERS_DB_URL")
if not USERS_DB_URL:
    logger.critical("Environment variable USERS_DB_URL must be set")
    raise RuntimeError("Environment variable USERS_DB_URL must be set")
AMQP_URL = os.getenv("AMQP_URL")
if not AMQP_URL:
    logger.critical("Environment variable AMQP_URL must be set")
    raise RuntimeError("Environment variable AMQP_URL must be set")
JWT_SECRET = os.getenv("JWT_SECRET", "secret")

# Initialize database schema
Base.metadata.create_all(bind=engine)

# gRPC port for Python service (Nginx handles /healthz)
GRPC_PORT = int(os.getenv("GRPC_PORT", "50052"))

# -----------------------------------------------------
# RabbitMQ helper with detailed logging
# -----------------------------------------------------

def publish_event(event_type: str, payload: dict):
    """Publish a user domain event to RabbitMQ with detailed logging."""
    start = datetime.utcnow()
    logger.info("[RabbitMQ] Connecting to broker at %s", AMQP_URL)
    conn = None
    try:
        params = pika.URLParameters(AMQP_URL)
        conn = pika.BlockingConnection(params)
        logger.info("[RabbitMQ] Connection established")

        ch = conn.channel()
        logger.debug("[RabbitMQ] Declaring exchange 'users' of type 'fanout'")
        ch.exchange_declare(exchange="users", exchange_type="fanout", durable=True)
        logger.info("[RabbitMQ] Exchange 'users' ready")

        message = json.dumps({"type": event_type, **payload})
        logger.debug("[RabbitMQ] Publishing message: %s", message)
        ch.basic_publish(
            exchange="users",
            routing_key="",
            body=message,
            properties=pika.BasicProperties(
                content_type='application/json',
                delivery_mode=2  # persistent
            )
        )
        logger.info("[RabbitMQ] Published event '%s' with payload %s", event_type, payload)

    except Exception as e:
        logger.error("[RabbitMQ] Failed to publish event '%s': %s", event_type, e, exc_info=True)
        raise
    finally:
        if conn and not conn.is_closed:
            try:
                conn.close()
                logger.info("[RabbitMQ] Connection closed")
            except Exception as close_err:
                logger.warning("[RabbitMQ] Error closing connection: %s", close_err, exc_info=True)
        elapsed = (datetime.utcnow() - start).total_seconds()
        logger.debug("[RabbitMQ] publish_event took %.3f seconds", elapsed)

# -----------------------------------------------------
# JWT utilities
# -----------------------------------------------------

def decode_token(token: str):
    try:
        decoded = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        logger.debug("[Auth] Token decoded for user %s", decoded.get("sub"))
        return decoded
    except jwt.PyJWTError as exc:
        logger.warning("[Auth] Invalid token: %s", exc)
        raise HTTPException(401, "Token inválido")

# -----------------------------------------------------
# gRPC Auth interceptor
# -----------------------------------------------------
class AuthInterceptor(ServerInterceptor):
    def __init__(self, logger_: logging.Logger):
        self._log = logger_

    def intercept_service(self, continuation: Callable, handler_call_details: grpc.HandlerCallDetails):
        handler = continuation(handler_call_details)
        if not handler:
            return None
        if handler.request_streaming or handler.response_streaming:
            return handler

        method = handler_call_details.method.split("/")[-1]

        def wrapper(request, context: ServicerContext):
            self._log.debug("[Auth] %s called", method)
            token_hdr = dict(context.invocation_metadata()).get("authorization", "")

            # Public CreateUser allows optional token
            if method == "CreateUser":
                if token_hdr:
                    data = decode_token(token_hdr.split()[1])
                    if request.role == RoleEnum.admin.value and data.get("role") != RoleEnum.admin.value:
                        self._log.info("[Auth] Unauthorized admin creation by %s", data.get("sub"))
                        context.abort(grpc.StatusCode.PERMISSION_DENIED,
                                      "Solo admin puede crear administradores")
                elif request.role == RoleEnum.admin.value:
                    self._log.info("[Auth] Missing token for admin creation")
                    context.abort(grpc.StatusCode.UNAUTHENTICATED,
                                  "Token requerido para crear admin")
                return handler.unary_unary(request, context)

            # Other methods require token
            if not token_hdr:
                self._log.info("[Auth] No token provided for %s", method)
                context.abort(grpc.StatusCode.UNAUTHENTICATED, "Token requerido")
            data = decode_token(token_hdr.split()[1])
            context.user = data
            return handler.unary_unary(request, context)

        return grpc.unary_unary_rpc_method_handler(
            wrapper,
            request_deserializer=handler.request_deserializer,
            response_serializer=handler.response_serializer,
        )

# -----------------------------------------------------
# gRPC UserService implementation
# -----------------------------------------------------
class UserService(users_pb2_grpc.UserServiceServicer):
    def CreateUser(self, req, ctx):
        logger.info("CreateUser | email=%s", req.email)
        db: Session = SessionLocal()
        if req.password != req.password_confirmation:
            logger.warning("Password mismatch for %s", req.email)
            ctx.abort(grpc.StatusCode.INVALID_ARGUMENT, "Las contraseñas no coinciden")
        if db.query(User).filter_by(email=req.email).first():
            logger.warning("Duplicate email registration attempt: %s", req.email)
            ctx.abort(grpc.StatusCode.ALREADY_EXISTS, "Email ya registrado")

        pwd_hash = bcrypt.hash(req.password)
        user = User(
            first_name=req.first_name,
            last_name=req.last_name,
            email=req.email,
            password_hash=pwd_hash,
            role=RoleEnum(req.role),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        publish_event("created", {
            "id": str(user.id),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
        })
        logger.info("User created | id=%s", user.id)
        ts = Timestamp()
        ts.FromDatetime(user.created_at)
        return users_pb2.UserResponse(user=users_pb2.User(
            id=str(user.id),
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            role=user.role.value,
            created_at=ts,
        ))

    def GetUserById(self, req, ctx):
        logger.debug("GetUserById | id=%s", req.id)
        db: Session = SessionLocal()
        u = db.query(User).get(uuid.UUID(req.id))
        if not u or u.deleted_at:
            logger.info("User not found | id=%s", req.id)
            ctx.abort(grpc.StatusCode.NOT_FOUND, "Usuario no encontrado")
        user_ctx = context.user
        if user_ctx["role"] != RoleEnum.admin.value and user_ctx["sub"] != req.id:
            logger.info("Forbidden access to %s by %s", req.id, user_ctx["sub"])
            ctx.abort(grpc.StatusCode.PERMISSION_DENIED, "No autorizado")
        ts = Timestamp()
        ts.FromDatetime(u.created_at)
        return users_pb2.UserResponse(user=users_pb2.User(
            id=req.id,
            first_name=u.first_name,
            last_name=u.last_name,
            email=u.email,
            role=u.role.value,
            created_at=ts,
        ))

    def UpdateUser(self, req, ctx):
        logger.info("UpdateUser | id=%s", req.id)
        db: Session = SessionLocal()
        u = db.query(User).get(uuid.UUID(req.id))
        if not u or u.deleted_at:
            logger.info("User not found for update | id=%s", req.id)
            ctx.abort(grpc.StatusCode.NOT_FOUND, "Usuario no encontrado")
        user_ctx = context.user
        if user_ctx["role"] != RoleEnum.admin.value and user_ctx["sub"] != req.id:
            logger.info("Forbidden update to %s by %s", req.id, user_ctx["sub"])
            ctx.abort(grpc.StatusCode.PERMISSION_DENIED, "No autorizado")
        u.first_name = req.first_name
        u.last_name = req.last_name
        u.email = req.email
        db.commit()
        db.refresh(u)
        publish_event("updated", {
            "id": str(u.id),
            "email": u.email,
            "first_name": u.first_name,
            "last_name": u.last_name,
        })
        logger.info("User updated | id=%s", u.id)
        ts = Timestamp()
        ts.FromDatetime(u.created_at)
        return users_pb2.UserResponse(user=users_pb2.User(
            id=req.id,
            first_name=u.first_name,
            last_name=u.last_name,
            email=u.email,
            role=u.role.value,
            created_at=ts,
        ))

    def DeleteUser(self, req, ctx):
        logger.info("DeleteUser | id=%s", req.id)
        db: Session = SessionLocal()
        u = db.query(User).get(uuid.UUID(req.id))
        if not u or u.deleted_at:
            logger.info("User not found for delete | id=%s", req.id)
            ctx.abort(grpc.StatusCode.NOT_FOUND, "Usuario no encontrado")
        if context.user["role"] != RoleEnum.admin.value:
            logger.info("Forbidden delete of %s by %s", req.id, context.user["sub"])
            ctx.abort(grpc.StatusCode.PERMISSION_DENIED, "Solo admin puede eliminar")
        u.deleted_at = datetime.utcnow()
        db.commit()
        publish_event("deleted", {"id": req.id})
        logger.info("User deleted | id=%s", req.id)
        return users_pb2.Empty()

    def ListUsers(self, req, ctx):
        logger.debug("ListUsers")
        if context.user["role"] != RoleEnum.admin.value:
            logger.info("Forbidden list users by %s", context.user["sub"])
            ctx.abort(grpc.StatusCode.PERMISSION_DENIED, "Solo admin puede listar usuarios")
        db: Session = SessionLocal()
        q = db.query(User).filter(User.deleted_at.is_(None))
        if req.email:
            q = q.filter(User.email.ilike(f"%{req.email}%"))
        if req.first_name:
            q = q.filter(User.first_name.ilike(f"%{req.first_name}%"))
        if req.last_name:
            q = q.filter(User.last_name.ilike(f"%{req.last_name}%"))
        users_out = []
        for u in q.all():
            ts = Timestamp()
            ts.FromDatetime(u.created_at)
            users_out.append(users_pb2.User(
                id=str(u.id),
                first_name=u.first_name,
                last_name=u.last_name,
                email=u.email,
                role=u.role.value,
                created_at=ts,
            ))
        logger.info("Listed %d users", len(users_out))
        return users_pb2.ListUsersResponse(users=users_out)

# -----------------------------------------------------
# Server bootstrap
# -----------------------------------------------------
def serve():
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        interceptors=[AuthInterceptor(logger)],
    )
    users_pb2_grpc.add_UserServiceServicer_to_server(UserService(), server)
    server.add_insecure_port(f"[::]:{GRPC_PORT}")
    logger.info("UserService gRPC listening on port %s", GRPC_PORT)
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
