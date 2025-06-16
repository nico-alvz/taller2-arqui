import os
import json
import uuid
from concurrent import futures
from datetime import datetime

import pika
import jwt
import grpc
from grpc import ServicerContext
from google.protobuf.timestamp_pb2 import Timestamp
from sqlalchemy.orm import Session

from db import SessionLocal, engine
from models import Base, Playlist, PlaylistVideo
import proto.playlist_pb2 as playlist_pb2
import proto.playlist_pb2_grpc as playlist_pb2_grpc
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv(os.getenv('ENV_PATH', '.env'))

# Inicializar DB y RabbitMQ
Base.metadata.create_all(bind=engine)
AMQP_URL = os.getenv('AMQP_URL')
JWT_SECRET = os.getenv('JWT_SECRET', 'secret')

# Función helper para publicar eventos

def publish_event(event: str, payload: dict):
    params = pika.URLParameters(AMQP_URL)
    with pika.BlockingConnection(params) as conn:
        ch = conn.channel()
        ch.exchange_declare(exchange='playlists', exchange_type='fanout')
        message = json.dumps({'event': event, **payload})
        ch.basic_publish(exchange='playlists', routing_key='', body=message)

# Decodificador de JWT
def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
    except jwt.PyJWTError:
        raise grpc.RpcError(grpc.StatusCode.UNAUTHENTICATED, 'Token inválido')

# Interceptor de autenticación
def auth_interceptor(method, request, context: ServicerContext, next_call):
    meta = dict(context.invocation_metadata())
    auth = meta.get('authorization')
    if not auth:
        context.abort(grpc.StatusCode.UNAUTHENTICATED, 'Token requerido')
    token = auth.split()[1]
    context.user = decode_token(token)
    return next_call(request, context)

# Implementación del servicio gRPC
class PlaylistService(playlist_pb2_grpc.PlaylistServiceServicer):

    def CreatePlaylist(self, request, context: ServicerContext):
        db: Session = SessionLocal()
        owner_id = context.user.get('sub')
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

    def GetPlaylist(self, request, context: ServicerContext):
        db: Session = SessionLocal()
        playlist = db.query(Playlist).get(uuid.UUID(request.id))
        if not playlist:
            context.abort(grpc.StatusCode.NOT_FOUND, 'Playlist no encontrada')
        owner_id = context.user.get('sub')
        if playlist.owner_id.hex != owner_id and context.user.get('role') != 'Administrador':
            context.abort(grpc.StatusCode.PERMISSION_DENIED, 'No autorizado')
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

    def UpdatePlaylist(self, request, context: ServicerContext):
        db: Session = SessionLocal()
        playlist = db.query(Playlist).get(uuid.UUID(request.id))
        if not playlist:
            context.abort(grpc.StatusCode.NOT_FOUND, 'Playlist no encontrada')
        owner_id = context.user.get('sub')
        if playlist.owner_id.hex != owner_id and context.user.get('role') != 'Administrador':
            context.abort(grpc.StatusCode.PERMISSION_DENIED, 'No autorizado')
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

    def DeletePlaylist(self, request, context: ServicerContext):
        db: Session = SessionLocal()
        playlist = db.query(Playlist).get(uuid.UUID(request.id))
        if not playlist:
            context.abort(grpc.StatusCode.NOT_FOUND, 'Playlist no encontrada')
        owner_id = context.user.get('sub')
        if playlist.owner_id.hex != owner_id and context.user.get('role') != 'Administrador':
            context.abort(grpc.StatusCode.PERMISSION_DENIED, 'No autorizado')
        db.delete(playlist)
        db.commit()
        publish_event('playlist.deleted', {'id': request.id})
        return playlist_pb2.Empty()

    def ListPlaylists(self, request, context: ServicerContext):
        db: Session = SessionLocal()
        owner_id = context.user.get('sub')
        playlists = db.query(Playlist).filter_by(owner_id=uuid.UUID(owner_id)).all()
        response = []
        for p in playlists:
            ts = Timestamp()
            ts.FromDatetime(p.created_at)
            response.append(playlist_pb2.Playlist(
                id=str(p.id),
                name=p.name,
                description=p.description,
                owner_id=p.owner_id.hex,
                created_at=ts
            ))
        return playlist_pb2.ListPlaylistsResponse(playlists=response)

    def AddVideo(self, request, context: ServicerContext):
        db: Session = SessionLocal()
        playlist = db.query(Playlist).get(uuid.UUID(request.playlist_id))
        if not playlist:
            context.abort(grpc.StatusCode.NOT_FOUND, 'Playlist no encontrada')
        owner_id = context.user.get('sub')
        if playlist.owner_id.hex != owner_id:
            context.abort(grpc.StatusCode.PERMISSION_DENIED, 'No autorizado')
        entry = PlaylistVideo(
            playlist_id=uuid.UUID(request.playlist_id),
            video_id=request.video_id
        )
        db.add(entry)
        db.commit()
        publish_event('playlist.video_added', {'playlist_id': request.playlist_id, 'video_id': request.video_id})
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

    def ListVideos(self, request, context: ServicerContext):
        db: Session = SessionLocal()
        entries = db.query(PlaylistVideo).filter_by(playlist_id=uuid.UUID(request.playlist_id)).all()
        videos = []
        for e in entries:
            ts = Timestamp()
            ts.FromDatetime(e.added_at)
            videos.append(playlist_pb2.VideoEntry(video_id=e.video_id, added_at=ts))
        return playlist_pb2.ListVideosResponse(videos=videos)

# Función de arranque del servidor
def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10), interceptors=[auth_interceptor])
    playlist_pb2_grpc.add_PlaylistServiceServicer_to_server(PlaylistService(), server)
    server.add_insecure_port('[::]:50052')
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()