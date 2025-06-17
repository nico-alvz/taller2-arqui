import os
import json
import uuid
import logging
from concurrent import futures
from datetime import datetime
from typing import Callable
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

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

# Initialize DB schema
Base.metadata.create_all(bind=engine)

# Default ports
GRPC_PORT = int(os.getenv("PORT", "50051"))
HEALTH_PORT = int(os.getenv("HEALTH_PORT", str(GRPC_PORT + 1)))

# -----------------------------------------------------
# RabbitMQ helper
# -----------------------------------------------------
def publish_event(event_type: str, payload: dict):
    logger.debug("Publishing event '%s' (id=%s)", event_type, payload.get("id"))
    params = pika.URLParameters(AMQP_URL)
    conn = pika.BlockingConnection(params)
    ch = conn.channel()
    ch.exchange_declare(exchange="users", exchange_type="fanout")
    ch.basic_publish(exchange="users", routing_key="", body=json.dumps({"type": event_type, **payload}))
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
                        context.abort(grpc.StatusCode.PERMISSION_DENIED, "Solo admin puede crear administradores")
                elif request.role == RoleEnum.admin.value:
                    context.abort(grpc.StatusCode.UNAUTHENTICATED, "Token requerido para crear admin")
                return handler.unary_unary(request, context)
            # Other methods
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
# gRPC UserService (omitted methods)...
# -----------------------------------------------------
class UserService(users_pb2_grpc.UserServiceServicer):
    pass  # implement CreateUser, GetUserById, etc.

# -----------------------------------------------------
# HTTP health-check for Render
# -----------------------------------------------------
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ('/', '/healthz'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK - Render health check')
        else:
            self.send_response(404)
            self.end_headers()

    def do_HEAD(self):
        if self.path in ('/', '/healthz'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

def start_health_server():
    logger.info(f"Render health server on /healthz listening at port {HEALTH_PORT}")
    HTTPServer(('', HEALTH_PORT), HealthHandler).serve_forever()

# -----------------------------------------------------
# Server bootstrap
# -----------------------------------------------------
def serve():
    # Start HTTP health-check on separate port
    threading.Thread(target=start_health_server, daemon=True).start()

    # Start gRPC server
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
