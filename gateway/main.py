from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import grpc
import httpx
from jose import jwt
import os

# Import generated stubs
from gen import users_pb2, users_pb2_grpc
from gen import playlist_pb2, playlist_pb2_grpc

app = FastAPI(title="API Gateway")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
SECRET_KEY = os.getenv("JWT_SECRET", "secret")

# Service addresses
AUTH_URL     = os.getenv("AUTH_SERVICE_URL", "http://auth_service:8000")
USERS_GRPC   = os.getenv("USERS_SERVICE_ADDR", "users_service:50051")
PLAYLIST_GRPC= os.getenv("PLAYLIST_SERVICE_ADDR", "playlist_service:50052")
MONITOR_URL  = os.getenv("MONITOR_SERVICE_URL", "http://monitoring_service:8004")

# JWT extraction
async def get_token(token: str = Depends(oauth2_scheme)) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return token
    except jwt.JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

# Health
@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

# Auth endpoints (HTTP proxy)
@app.post("/auth/login")
async def login(request: Request):
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{AUTH_URL}/auth/login", json=await request.json())
    resp.raise_for_status()
    return resp.json()

# Users endpoints (gRPC)
def get_user_stub():
    channel = grpc.insecure_channel(USERS_GRPC)
    return users_pb2_grpc.UserServiceStub(channel)

@app.post("/usuarios", status_code=status.HTTP_201_CREATED)
async def create_user(request: Request):
    payload = await request.json()
    stub = get_user_stub()
    req = users_pb2.CreateUserRequest(**payload)
    resp = stub.CreateUser(req)
    return resp.user

@app.get("/usuarios/{user_id}")
async def get_user(user_id: str, token: str = Depends(get_token)):
    stub = get_user_stub()
    req = users_pb2.GetUserByIdRequest(id=user_id)
    resp = stub.GetUserById(req, metadata=[('authorization', f'Bearer {token}')])
    return resp.user

@app.patch("/usuarios/{user_id}")
async def update_user(user_id: str, request: Request, token: str = Depends(get_token)):
    data = await request.json()
    stub = get_user_stub()
    req = users_pb2.UpdateUserRequest(id=user_id, **data)
    resp = stub.UpdateUser(req, metadata=[('authorization', f'Bearer {token}')])
    return resp.user

@app.delete("/usuarios/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: str, token: str = Depends(get_token)):
    stub = get_user_stub()
    req = users_pb2.DeleteUserRequest(id=user_id)
    stub.DeleteUser(req, metadata=[('authorization', f'Bearer {token}')])
    return None

@app.get("/usuarios")
async def list_users(token: str = Depends(get_token)):
    stub = get_user_stub()
    req = users_pb2.ListUsersRequest()
    resp = stub.ListUsers(req, metadata=[('authorization', f'Bearer {token}')])
    return list(resp.users)

# Playlist endpoints (gRPC)
def get_playlist_stub():
    channel = grpc.insecure_channel(PLAYLIST_GRPC)
    return playlist_pb2_grpc.PlaylistServiceStub(channel)

@app.post("/listas-reproduccion", status_code=status.HTTP_201_CREATED)
async def create_playlist(request: Request, token: str = Depends(get_token)):
    data = await request.json()
    stub = get_playlist_stub()
    req = playlist_pb2.CreatePlaylistRequest(**data)
    resp = stub.CreatePlaylist(req, metadata=[('authorization', f'Bearer {token}')])
    return resp.playlist

@app.post("/listas-reproduccion/{playlist_id}/videos")
async def add_video(playlist_id: str, request: Request, token: str = Depends(get_token)):
    data = await request.json()
    video_id = data.get('video_id')
    stub = get_playlist_stub()
    req = playlist_pb2.AddVideoRequest(playlist_id=playlist_id, video_id=video_id)
    resp = stub.AddVideo(req, metadata=[('authorization', f'Bearer {token}')])
    return resp.playlist

@app.delete("/listas-reproduccion/{playlist_id}/videos", status_code=status.HTTP_204_NO_CONTENT)
async def remove_video(playlist_id: str, request: Request, token: str = Depends(get_token)):
    data = await request.json()
    video_id = data.get('video_id')
    stub = get_playlist_stub()
    req = playlist_pb2.RemoveVideoRequest(playlist_id=playlist_id, video_id=video_id)
    stub.RemoveVideo(req, metadata=[('authorization', f'Bearer {token}')])
    return None

@app.get("/listas-reproduccion")
async def list_playlists(token: str = Depends(get_token)):
    stub = get_playlist_stub()
    req = playlist_pb2.ListPlaylistsRequest()
    resp = stub.ListPlaylists(req, metadata=[('authorization', f'Bearer {token}')])
    return list(resp.playlists)

@app.delete("/listas-reproduccion/{playlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_playlist(playlist_id: str, token: str = Depends(get_token)):
    stub = get_playlist_stub()
    req = playlist_pb2.DeletePlaylistRequest(id=playlist_id)
    stub.DeletePlaylist(req, metadata=[('authorization', f'Bearer {token}')])
    return None
