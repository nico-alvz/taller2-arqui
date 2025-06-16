from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import grpc.aio
from jose import jwt
from fastapi.responses import JSONResponse
import os

# Stub imports
from gen import users_pb2, users_pb2_grpc, playlist_pb2, playlist_pb2_grpc

# Load .env variables
load_dotenv()

# Settings via Pydantic v2
from pydantic import ConfigDict

class Settings(BaseSettings):
    # Load .env and ignore any extra keys
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    jwt_secret: str
    auth_service_url: str
    users_service_addr: str
    playlist_service_addr: str
    monitor_service_url: str

settings = Settings()

# FastAPI app
app = FastAPI(title="API Gateway")

# Configure logging
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")  # full URL for OAuth2 flow

# JWT extraction dependency
def get_token(token: str = Depends(oauth2_scheme)) -> str:
    try:
        jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return token
    except jwt.JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

# Health check
@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

# Auth proxy (HTTP)
import requests

@app.post("/auth/login")
async def login(request: Request):
    payload = await request.json()
    logger.debug(f"Auth login payload: {payload}")
    # Parse AUTH_SERVICE_URL and build full auth URL
    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(settings.auth_service_url)
    scheme = parsed.scheme or 'https'
    netloc = parsed.netloc or parsed.path
    # If scheme is https and explicit port 8000 was included, strip it
    if scheme == 'https' and netloc.endswith(':8000'):
        netloc = netloc[:-5]
    auth_url = urlunparse((scheme, netloc, '/auth/login', '', '', ''))
    logger.debug(f"Calling auth service at: {auth_url}")
    try:
        # Synchronous HTTP call to match curl behavior
        resp = requests.post(
            auth_url,
            json=payload,
            headers={"Accept": "application/json"},
            timeout=(5, 10)
        )
        resp.raise_for_status()
    except requests.exceptions.ConnectTimeout:
        logger.error(f"Timeout connecting to auth service at {auth_url}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Auth service unreachable")
    except requests.exceptions.HTTPError as e:
        logger.error(f"Auth service HTTP error: {e}")
        code = e.response.status_code if e.response is not None else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=code, detail="Auth service error")
    except requests.exceptions.RequestException as e:
        logger.error(f"Auth service request error: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Auth service error")
    return JSONResponse(content=resp.json(), status_code=resp.status_code)

# gRPC stubs
def get_user_stub():
    channel = grpc.aio.insecure_channel(settings.users_service_addr)
    return users_pb2_grpc.UserServiceStub(channel)

def get_playlist_stub():
    channel = grpc.aio.insecure_channel(settings.playlist_service_addr)
    return playlist_pb2_grpc.PlaylistServiceStub(channel)

# Helper for errors
def handle_rpc_error(e, method_name: str):
    code = e.code().name if hasattr(e, 'code') else 'UNKNOWN'
    details = e.details() if hasattr(e, 'details') else str(e)
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"gRPC {method_name} failed ({code}): {details}"
    )

# Users endpoints
@app.post("/usuarios", status_code=status.HTTP_201_CREATED)
async def create_user(request: Request):
    # Parse incoming JSON
    payload = await request.json()
    logger.debug(f"create_user payload: {payload}")

    # The role field is a plain string in the proto, so forward as-is
    role_str = payload.get('role', '')

    # Build the gRPC request
    try:
        req = users_pb2.CreateUserRequest(
            first_name=payload.get('first_name', ''),
            last_name=payload.get('last_name', ''),
            email=payload.get('email', ''),
            password=payload.get('password', ''),
            password_confirmation=payload.get('password_confirmation', ''),
            role=role_str,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid create payload: {e}"
        )

    # Call the gRPC stub
    stub = get_user_stub()
    try:
        resp = await stub.CreateUser(req)
    except grpc.RpcError as e:
        detail = e.details() if hasattr(e, 'details') else str(e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"gRPC CreateUser failed: {detail}"
        )
    return resp.user

# Playlist endpoints
@app.post("/listas-reproduccion", status_code=status.HTTP_201_CREATED)
async def create_playlist(request: Request, token: str = Depends(get_token)):

    data = await request.json()
    stub = get_playlist_stub()
    req = playlist_pb2.CreatePlaylistRequest(**data)
    try:
        resp = await stub.CreatePlaylist(req, metadata=[('authorization', f'Bearer {token}')])
    except grpc.RpcError as e:
        handle_rpc_error(e, 'CreatePlaylist')
    return resp.playlist

@app.post("/listas-reproduccion/{playlist_id}/videos")
async def add_video(playlist_id: str, request: Request, token: str = Depends(get_token)):

    data = await request.json()
    stub = get_playlist_stub()
    req = playlist_pb2.AddVideoRequest(playlist_id=playlist_id, video_id=data.get('video_id'))
    try:
        resp = await stub.AddVideo(req, metadata=[('authorization', f'Bearer {token}')])
    except grpc.RpcError as e:
        handle_rpc_error(e, 'AddVideo')
    return resp.playlist

@app.delete("/listas-reproduccion/{playlist_id}/videos", status_code=status.HTTP_204_NO_CONTENT)
async def remove_video(playlist_id: str, request: Request, token: str = Depends(get_token)):

    data = await request.json()
    stub = get_playlist_stub()
    req = playlist_pb2.RemoveVideoRequest(playlist_id=playlist_id, video_id=data.get('video_id'))
    try:
        await stub.RemoveVideo(req, metadata=[('authorization', f'Bearer {token}')])
    except grpc.RpcError as e:
        handle_rpc_error(e, 'RemoveVideo')
    return None

@app.get("/listas-reproduccion")
async def list_playlists(token: str = Depends(get_token)):

    stub = get_playlist_stub()
    req = playlist_pb2.ListPlaylistsRequest()
    try:
        resp = await stub.ListPlaylists(req, metadata=[('authorization', f'Bearer {token}')])
    except grpc.RpcError as e:
        handle_rpc_error(e, 'ListPlaylists')
    return list(resp.playlists)

@app.delete("/listas-reproduccion/{playlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_playlist(playlist_id: str, token: str = Depends(get_token)):

    stub = get_playlist_stub()
    req = playlist_pb2.DeletePlaylistRequest(id=playlist_id)
    try:
        await stub.DeletePlaylist(req, metadata=[('authorization', f'Bearer {token}')])
    except grpc.RpcError as e:
        handle_rpc_error(e, 'DeletePlaylist')
    return None

# Entry point
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
