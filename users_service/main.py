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

from db import SessionLocal, engine
from models import Base, User, RoleEnum
from gen import users_pb2, users_pb2_grpc
from dotenv import load_dotenv
from passlib.hash import bcrypt

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
dotenv_path = os.getenv("ENV_PATH", ".env")
load_dotenv(dotenv_path)

# Ensure DATABASE_URL is set
DATABASE_URL = os.getenv("USERS_DB_URL")
if not DATABASE_URL:
    logger.critical("Environment variable DATABASE_URL must be set")
    raise RuntimeError("Environment variable DATABASE_URL must be set")

# Initialize DB schema
Base.metadata.create_all(bind=engine)
AMQP_URL = os.getenv("AMQP_URL")
if not AMQP_URL:
    logger.critical("Environment variable AMQP_URL must be set")
    raise RuntimeError("Environment variable AMQP_URL must be set")
JWT_SECRET = os.getenv("JWT_SECRET", "secret")

# -----------------------------------------------------
# Helper: Publish events to RabbitMQ
# -----------------------------------------------------

def publish_event(event_type: str, payload: dict):
    """Publish a user domain event to the fanout exchange."""
    logger.debug("Publishing event '%s' (id=%s)", event_type, payload.get("id"))
    params = pika.URLParameters(AMQP_URL)
    conn = pika.BlockingConnection(params)
    ch = conn.channel()
    ch.exchange_declare(exchange="users", exchange_type="fanout")
    message = json.dumps({"type": event_type, **payload})
    ch.basic_publish(exchange="users", routing_key="", body=message)
    conn.close()

# -----------------------------------------------------
# JWT utils
# -----------------------------------------------------

def decode_token(token: str):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        logger.warning("Token inválido: %s", exc)
        raise HTTPException(401, "Token inválido")

# -----------------------------------------------------
# Authentication / authorization interceptor (gRPC v1.63+)
# -----------------------------------------------------

class AuthInterceptor(ServerInterceptor):
    """gRPC server interceptor that enforces JWT‑based auth rules."""

    def __init__(self, logger_: logging.Logger):
        self._log = logger_

    # pylint: disable=arguments-differ
    def intercept_service(self, continuation: Callable, handler_call_details: grpc.HandlerCallDetails):
        """Wrap unary‑unary calls with auth logic."""
        handler = continuation(handler_call_details)
        if handler is None:
            return None  # pragma: no cover

        # We only have unary‑unary methods in this service.
        if handler.request_streaming or handler.response_streaming:
            return handler

        method_name = handler_call_details.method.split("/")[-1]  # eg. /UserService/CreateUser → CreateUser

        def unary_unary_interceptor(request, context: ServicerContext):
            self._log.debug("%s called", method_name)

            # ------- Public endpoint: CreateUser -------
            if method_name == "CreateUser":
                token_hdr = dict(context.invocation_metadata()).get("authorization", "")
                if token_hdr:
                    data = decode_token(token_hdr.split()[1])
                    # Only admins can create admins
                    if request.role == RoleEnum.admin.value and data.get("role") != RoleEnum.admin.value:
                        self._log.info("Unauthorized attempt to create admin by user %s", data.get("sub"))
                        context.abort(grpc.StatusCode.PERMISSION_DENIED, "Solo admin puede crear administradores")
                else:
                    if request.role == RoleEnum.admin.value:
                        self._log.info("Anonymous attempt to create admin rejected")
                        context.abort(grpc.StatusCode.UNAUTHENTICATED, "Token requerido para crear admin")

                return handler.unary_unary(request, context)

            # ------- All other endpoints require token -------
            token_hdr = dict(context.invocation_metadata()).get("authorization", "")
            if not token_hdr:
                self._log.info("Request to %s without token", method_name)
                context.abort(grpc.StatusCode.UNAUTHENTICATED, "Token requerido")
            data = decode_token(token_hdr.split()[1])
            context.user = data  # Attach user info for downstream business logic

            return handler.unary_unary(request, context)

        return grpc.unary_unary_rpc_method_handler(
            unary_unary_interceptor,
            request_deserializer=handler.request_deserializer,
            response_serializer=handler.response_serializer,
        )

# -----------------------------------------------------
# gRPC Service implementation
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
        user_ctx = ctx.user
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
        user_ctx = ctx.user
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
        if ctx.user["role"] != RoleEnum.admin.value:
            logger.info("Forbidden delete of %s by %s", req.id, ctx.user["sub"])
            ctx.abort(grpc.StatusCode.PERMISSION_DENIED, "Solo admin puede eliminar")
        u.deleted_at = datetime.utcnow()
        db.commit()
        publish_event("deleted", {"id": req.id})
        logger.info("User deleted | id=%s", req.id)
        return users_pb2.Empty()

    def ListUsers(self, req, ctx):
        logger.debug("ListUsers")
        if ctx.user["role"] != RoleEnum.admin.value:
            logger.info("Forbidden list users by %s", ctx.user["sub"])
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
# gRPC server bootstrap
# -----------------------------------------------------

def serve():
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        interceptors=[AuthInterceptor(logger)],
    )
    users_pb2_grpc.add_UserServiceServicer_to_server(UserService(), server)
    server.add_insecure_port("[::]:50051")
    logger.info("UserService gRPC escuchando en puerto 50051")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()

