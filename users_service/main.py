#!/usr/bin/env python3
import os
import json
import uuid
import logging
from concurrent import futures
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

USERS_DB_URL = os.getenv("USERS_DB_URL")
if not USERS_DB_URL:
    logger.critical("Environment variable USERS_DB_URL must be set")
    raise RuntimeError("Environment variable USERS_DB_URL must be set")

AMQP_URL = os.getenv("AMQP_URL")
if not AMQP_URL:
    logger.critical("Environment variable AMQP_URL must be set")
    raise RuntimeError("Environment variable AMQP_URL must be set")

JWT_SECRET = os.getenv("JWT_SECRET", "secret")

# -----------------------------------------------------
# Initialize database schema
# -----------------------------------------------------
Base.metadata.create_all(bind=engine)

# -----------------------------------------------------
# Ports
# -----------------------------------------------------
# gRPC is served here; nginx will listen on $PORT and proxy to this.
GRPC_PORT = int(os.getenv("GRPC_PORT", "50052"))

# -----------------------------------------------------
# RabbitMQ helper
# -----------------------------------------------------
def publish_event(event_type: str, payload: dict):
    logger.debug("Publishing event '%s' (id=%s)", event_type, payload.get("id"))
    params = pika.URLParameters(AMQP_URL)
    conn = pika.BlockingConnection(params)
    ch = conn.channel()
    ch.exchange_declare(exchange="users", exchange_type="fanout")
    ch.basic_publish(
        exchange="users",
        routing_key="",
        body=json.dumps({"type": event_type, **payload})
    )
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
# Auth interceptor
# -----------------------------------------------------
class AuthInterceptor(ServerInterceptor):
    def __init__(self, logger_: logging.Logger):
        self._log = logger_

    def intercept_service(self, continuation: Callable, handler_call_details: grpc.HandlerCallDetails):
        handler = continuation(handler_call_details)
        if not handler:
            return None
        # Only unary-unary methods
        if handler.request_streaming or handler.response_streaming:
            return handler

        method = handler_call_details.method.split("/")[-1]

        def wrapper(request, context: ServicerContext):
            self._log.debug("%s called", method)
            token_hdr = dict(context.invocation_metadata()).get("authorization", "")
            # Public CreateUser
            if method == "CreateUser":
                if token_hdr:
                    data = decode_token(token_hdr.split()[1])
                    if request.role == RoleEnum.admin.value and data.get("role") != RoleEnum.admin.value:
                        context.abort(grpc.StatusCode.PERMISSION_DENIED,
                                      "Solo admin puede crear administradores")
                elif request.role == RoleEnum.admin.value:
                    context.abort(grpc.StatusCode.UNAUTHENTICATED,
                                  "Token requerido para crear admin")
                return handler.unary_unary(request, context)

            # All other methods require a valid token
            if not token_hdr:
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
# UserService implementation
# -----------------------------------------------------
class UserService(users_pb2_grpc.UserServiceServicer):
    def CreateUser(self, req, ctx):
        # ... tu lógica de CreateUser tal y como la tenías ...
        pass

    def GetUserById(self, req, ctx):
        # ... lógica de GetUserById ...
        pass

    def UpdateUser(self, req, ctx):
        # ... lógica de UpdateUser ...
        pass

    def DeleteUser(self, req, ctx):
        # ... lógica de DeleteUser ...
        pass

    def ListUsers(self, req, ctx):
        # ... lógica de ListUsers ...
        pass

# -----------------------------------------------------
# gRPC server bootstrap
# -----------------------------------------------------
def serve():
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        interceptors=[AuthInterceptor(logger)],
    )
    users_pb2_grpc.add_UserServiceServicer_to_server(UserService(), server)
    server.add_insecure_port(f"[::]:{GRPC_PORT}")
    logger.info(f"UserService gRPC listening on port {GRPC_PORT}")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
