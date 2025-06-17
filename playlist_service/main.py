#!/usr/bin/env python3
import os
import sys
import json
import uuid
import logging
from concurrent import futures

import pika
import jwt
import grpc
from grpc import ServerInterceptor, StatusCode
from google.protobuf.timestamp_pb2 import Timestamp
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

HERE = os.path.dirname(__file__)
GEN_DIR = os.path.join(HERE, 'gen')
if GEN_DIR not in sys.path:
    sys.path.insert(0, GEN_DIR)

import playlist_pb2
import playlist_pb2_grpc
from db import SessionLocal, engine
from models import Base, Playlist, PlaylistVideo

AMQP_URL = os.getenv('AMQP_URL')
if not AMQP_URL:
    raise RuntimeError("AMQP_URL environment variable is not set!")
JWT_SECRET = os.getenv('JWT_SECRET', 'secret')

# Ensure our tables exist
Base.metadata.create_all(bind=engine)
logging.info("✔️  Database tables created or verified")

def publish_event(event, payload):
    logging.info(f"→ Connecting to RabbitMQ at {AMQP_URL}")
    params = pika.URLParameters(AMQP_URL)
    with pika.BlockingConnection(params) as conn:
        logging.info("✔️  RabbitMQ connection established")
        ch = conn.channel()
        ch.exchange_declare(exchange='playlists', exchange_type='fanout')
        message = json.dumps({'event': event, **payload})
        ch.basic_publish(exchange='playlists', routing_key='', body=message)
    logging.info(f"✔️  Published event '{event}' with payload {payload}")

def decode_token(token):
    try:
        decoded = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        logging.info(f"✔️  Token decoded for user {decoded.get('sub')}")
        return decoded
    except jwt.PyJWTError:
        # Abort with proper gRPC status
        raise grpc.RpcError((StatusCode.UNAUTHENTICATED, 'Token inválido'))

class AuthInterceptor(ServerInterceptor):
    """
    A gRPC interceptor that enforces presence of a Bearer JWT
    and decodes it into context.user.
    """
    def intercept_service(self, continuation, handler_call_details):
        handler = continuation(handler_call_details)
        if handler is None:
            return None

        # Only wrap unary-unary RPCs (all our methods are unary-unary)
        if handler.unary_unary:
            def unary_unary_wrapper(request, context):
                # Extract and validate Authorization metadata
                md = dict(context.invocation_metadata())
                auth = md.get('authorization')
                if not auth:
                    context.abort(StatusCode.UNAUTHENTICATED, 'Token requerido')
                try:
                    token = auth.split()[1]
                except Exception:
                    context.abort(StatusCode.UNAUTHENTICATED, 'Formato de token inválido')
                # Decode and attach to context
                decoded = decode_token(token)
                context.user = decoded
                logging.info(f"🔐  Authenticated user {decoded.get('sub')} for {handler_call_details.method}")
                # Call original handler
                return handler.unary_unary(request, context)

            return grpc.unary_unary_rpc_method_handler(
                unary_unary_wrapper,
                request_deserializer=handler.request_deserializer,
                response_serializer=handler.response_serializer,
            )

        # For other styles (streams), you could similarly wrap stream handlers here...
        return handler


class PlaylistService(playlist_pb2_grpc.PlaylistServiceServicer):
    def CreatePlaylist(self, request, context):
        db = SessionLocal()
        owner_id = context.user.get('sub')
        logging.info(f"✚  CreatePlaylist called by {owner_id}")
        playlist = Playlist(
            name=request.name,
            description=request.description,
            owner_id=uuid.UUID(owner_id)
        )
        db.add(playlist)
        db.commit()
        db.refresh(playlist)
        publish_event('playlist.created', {'id': str(playlist.id), 'owner_id': owner_id})

        ts = Timestamp()
        ts.FromDatetime(playlist.created_at)
        return playlist_pb2.PlaylistResponse(
            playlist=playlist_pb2.Playlist(
                id=str(playlist.id),
                name=playlist.name,
                description=playlist.description,
                owner_id=owner_id,
                created_at=ts
            )
        )

    def GetPlaylist(self, request, context):
        db = SessionLocal()
        playlist = db.query(Playlist).get(uuid.UUID(request.id))
        owner_id = context.user.get('sub')
        logging.info(f"🔍  GetPlaylist {request.id} requested by {owner_id}")
        if not playlist:
            context.abort(StatusCode.NOT_FOUND, 'Playlist no encontrada')
        if playlist.owner_id.hex != owner_id and context.user.get('role') != 'Administrador':
            context.abort(StatusCode.PERMISSION_DENIED, 'No autorizado')

        ts = Timestamp()
        ts.FromDatetime(playlist.created_at)
        return playlist_pb2.PlaylistResponse(
            playlist=playlist_pb2.Playlist(
                id=str(playlist.id),
                name=playlist.name,
                description=playlist.description,
                owner_id=playlist.owner_id.hex,
                created_at=ts
            )
        )

    def UpdatePlaylist(self, request, context):
        db = SessionLocal()
        playlist = db.query(Playlist).get(uuid.UUID(request.id))
        owner_id = context.user.get('sub')
        logging.info(f"✎  UpdatePlaylist {request.id} called by {owner_id}")
        if not playlist:
            context.abort(StatusCode.NOT_FOUND, 'Playlist no encontrada')
        if playlist.owner_id.hex != owner_id and context.user.get('role') != 'Administrador':
            context.abort(StatusCode.PERMISSION_DENIED, 'No autorizado')

        playlist.name = request.name
        playlist.description = request.description
        db.commit()
        publish_event('playlist.updated', {'id': str(playlist.id)})

        ts = Timestamp()
        ts.FromDatetime(playlist.created_at)
        return playlist_pb2.PlaylistResponse(
            playlist=playlist_pb2.Playlist(
                id=str(playlist.id),
                name=playlist.name,
                description=playlist.description,
                owner_id=playlist.owner_id.hex,
                created_at=ts
            )
        )

    def DeletePlaylist(self, request, context):
        db = SessionLocal()
        playlist = db.query(Playlist).get(uuid.UUID(request.id))
        owner_id = context.user.get('sub')
        logging.info(f"✖  DeletePlaylist {request.id} called by {owner_id}")
        if not playlist:
            context.abort(StatusCode.NOT_FOUND, 'Playlist no encontrada')
        if playlist.owner_id.hex != owner_id and context.user.get('role') != 'Administrador':
            context.abort(StatusCode.PERMISSION_DENIED, 'No autorizado')

        db.delete(playlist)
        db.commit()
        publish_event('playlist.deleted', {'id': request.id})
        return playlist_pb2.Empty()

    def ListPlaylists(self, request, context):
        db = SessionLocal()
        owner_id = context.user.get('sub')
        logging.info(f"📜  ListPlaylists called by {owner_id}")
        playlists = db.query(Playlist).filter_by(owner_id=uuid.UUID(owner_id)).all()

        items = []
        for p in playlists:
            ts = Timestamp()
            ts.FromDatetime(p.created_at)
            items.append(playlist_pb2.Playlist(
                id=str(p.id),
                name=p.name,
                description=p.description,
                owner_id=p.owner_id.hex,
                created_at=ts
            ))

        return playlist_pb2.ListPlaylistsResponse(playlists=items)

    def AddVideo(self, request, context):
        db = SessionLocal()
        playlist = db.query(Playlist).get(uuid.UUID(request.playlist_id))
        owner_id = context.user.get('sub')
        logging.info(f"➕  AddVideo {request.video_id} to {request.playlist_id} by {owner_id}")
        if not playlist:
            context.abort(StatusCode.NOT_FOUND, 'Playlist no encontrada')
        if playlist.owner_id.hex != owner_id:
            context.abort(StatusCode.PERMISSION_DENIED, 'No autorizado')

        entry = PlaylistVideo(
            playlist_id=uuid.UUID(request.playlist_id),
            video_id=request.video_id
        )
        db.add(entry)
        db.commit()
        publish_event('playlist.video_added', {
            'playlist_id': request.playlist_id,
            'video_id': request.video_id
        })

        ts = Timestamp()
        ts.FromDatetime(entry.added_at)
        return playlist_pb2.PlaylistResponse(
            playlist=playlist_pb2.Playlist(
                id=str(playlist.id),
                name=playlist.name,
                description=playlist.description,
                owner_id=playlist.owner_id.hex,
                created_at=ts
            )
        )

    def ListVideos(self, request, context):
        db = SessionLocal()
        logging.info(f"🎬  ListVideos for playlist {request.playlist_id}")
        entries = db.query(PlaylistVideo).filter_by(playlist_id=uuid.UUID(request.playlist_id)).all()

        videos = []
        for e in entries:
            ts = Timestamp()
            ts.FromDatetime(e.added_at)
            videos.append(playlist_pb2.VideoEntry(
                video_id=e.video_id,
                added_at=ts
            ))

        return playlist_pb2.ListVideosResponse(videos=videos)


def serve():
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        interceptors=[AuthInterceptor()]  
    )
    playlist_pb2_grpc.add_PlaylistServiceServicer_to_server(PlaylistService(), server)
    port = '[::]:50052'
    server.add_insecure_port(port)
    logging.info(f"🚀  gRPC server starting on {port}")
    server.start()
    server.wait_for_termination()


if __name__ == '__main__':
    serve()
