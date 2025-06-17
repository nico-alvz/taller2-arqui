from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import grpc.aio
from jose import jwt
from fastapi.responses import JSONResponse
import os
import logging
import json
import requests


# Stub imports
from gen import users_pb2, users_pb2_grpc
from gen import playlist_pb2, playlist_pb2_grpc
#from gen import billing_pb2, billing_pb2_grpc
#from gen import videos_pb2, videos_pb2_grpc
#from gen import monitor_pb2, monitor_pb2_grpc
#from gen import interactions_pb2, interactions_pb2_grpc

# Load .env variables
load_dotenv()

# Settings via Pydantic v2
from pydantic import ConfigDict
class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    jwt_secret: str
    auth_service_url: str
    users_service_addr: str
    playlist_service_addr: str
    billing_service_addr: str
    videos_service_addr: str
    monitor_service_addr: str
    interactions_service_addr: str
    rabbitmq_url: str
settings = Settings()

# FastAPI app
app = FastAPI(title="API Gateway")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# JWT dependency
def jwt_dependency(token: str = Depends(oauth2_scheme)) -> str:
    try:
        jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return token
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing token")

# gRPC stub helpers
async def get_user_stub():
    channel = grpc.aio.insecure_channel(settings.users_service_addr)
    return users_pb2_grpc.UserServiceStub(channel)
async def get_playlist_stub():
    channel = grpc.aio.insecure_channel(settings.playlist_service_addr)
    return playlist_pb2_grpc.PlaylistServiceStub(channel)
async def get_billing_stub():
    channel = grpc.aio.insecure_channel(settings.billing_service_addr)
    return billing_pb2_grpc.BillingServiceStub(channel)
async def get_videos_stub():
    channel = grpc.aio.insecure_channel(settings.videos_service_addr)
    return videos_pb2_grpc.VideoServiceStub(channel)
async def get_monitor_stub():
    channel = grpc.aio.insecure_channel(settings.monitor_service_addr)
    return monitor_pb2_grpc.MonitorServiceStub(channel)
async def get_interactions_stub():
    channel = grpc.aio.insecure_channel(settings.interactions_service_addr)
    return interactions_pb2_grpc.InteractionServiceStub(channel)

# RPC error handler
def handle_rpc_error(e, method: str):
    code = e.code().name if hasattr(e, 'code') else 'UNKNOWN'
    details = e.details() if hasattr(e, 'details') else str(e)
    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"gRPC {method} failed ({code}): {details}")

# Health check
@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

# Auth proxy
from urllib.parse import urlparse, urlunparse

def proxy_auth(path: str, payload: dict, token: str = None):
    parsed = urlparse(settings.auth_service_url)
    scheme = parsed.scheme or 'https'
    netloc = parsed.netloc or parsed.path
    if scheme == 'https' and netloc.endswith(':8000'):
        netloc = netloc[:-5]
    url = urlunparse((scheme, netloc, path, '', '', ''))
    headers = {"Accept": "application/json"}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    resp = requests.post(url, json=payload, headers=headers, timeout=(5,10))
    resp.raise_for_status()
    return resp.json(), resp.status_code

@app.post("/auth/login")
async def login(request: Request):
    data = await request.json()
    try:
        body, code = proxy_auth('/auth/login', data)
    except requests.exceptions.HTTPError as e:
        detail = e.response.text if e.response else str(e)
        raise HTTPException(status_code=e.response.status_code if e.response else status.HTTP_502_BAD_GATEWAY, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    return JSONResponse(content=body, status_code=code)

@app.post("/auth/logout")
async def logout(token: str = Depends(jwt_dependency)):
    try:
        body, code = proxy_auth('/auth/logout', {}, token)
    except requests.exceptions.HTTPError as e:
        detail = e.response.text if e.response else str(e)
        raise HTTPException(status_code=e.response.status_code if e.response else status.HTTP_502_BAD_GATEWAY, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    return JSONResponse(content=body, status_code=code)

@app.patch("/auth/usuarios/{user_id}")
async def update_password(user_id: str, request: Request, token: str = Depends(jwt_dependency)):
    data = await request.json()
    try:
        body, code = proxy_auth(f'/auth/usuarios/{user_id}', data, token)
    except requests.exceptions.HTTPError as e:
        detail = e.response.text if e.response else str(e)
        raise HTTPException(status_code=e.response.status_code if e.response else status.HTTP_502_BAD_GATEWAY, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    return JSONResponse(content=body, status_code=code)

# Users endpoints
@app.post("/usuarios", status_code=status.HTTP_201_CREATED)
async def create_user(request: Request):
    payload = await request.json()
    role = payload.get('role', '')
    # Si se está creando un usuario Administrador, validar token y rol admin
    if role.lower() == 'administrador':
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token requerido para crear administrador")
        token = auth_header.split(' ', 1)[1]
        try:
            claims = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        except Exception:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
        if claims.get('role', '').lower() != 'administrador':
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo administradores pueden crear usuarios con rol Administrador")
    # CREAR el usuario via gRPC
    stub = await get_user_stub()
    req = users_pb2.CreateUserRequest(
        first_name=payload.get('first_name',''), last_name=payload.get('last_name',''),
        email=payload.get('email',''), password=payload.get('password',''),
        password_confirmation=payload.get('password_confirmation',''), role=role
    )
    try:
        resp = await stub.CreateUser(req)
    except grpc.RpcError as e:
        handle_rpc_error(e, 'CreateUser')
    await publish_event('users', 'user.created', {'id': resp.user.id})
    return resp.user

@app.get("/usuarios/{user_id}")
async def get_user(user_id: str, token: str = Depends(jwt_dependency)):
    stub = await get_user_stub()
    try:
        resp = await stub.GetUser(users_pb2.GetUserRequest(id=user_id), metadata=[('authorization', f'Bearer {token}')])
    except grpc.RpcError as e:
        handle_rpc_error(e, 'GetUser')
    return resp.user

@app.patch("/usuarios/{user_id}")
async def update_user(user_id: str, request: Request, token: str = Depends(jwt_dependency)):
    payload = await request.json()
    stub = await get_user_stub()
    req = users_pb2.UpdateUserRequest(id=user_id,
        first_name=payload.get('first_name',''), last_name=payload.get('last_name',''), email=payload.get('email','')
    )
    try:
        resp = await stub.UpdateUser(req, metadata=[('authorization', f'Bearer {token}')])
    except grpc.RpcError as e:
        handle_rpc_error(e, 'UpdateUser')
    await publish_event('users', 'user.updated', {'id': user_id})
    return resp.user

@app.delete("/usuarios/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: str, token: str = Depends(jwt_dependency)):
    stub = await get_user_stub()
    try:
        await stub.DeleteUser(users_pb2.DeleteUserRequest(id=user_id), metadata=[('authorization', f'Bearer {token}')])
    except grpc.RpcError as e:
        handle_rpc_error(e, 'DeleteUser')
    await publish_event('users', 'user.deleted', {'id': user_id})
    return None

@app.get("/usuarios")
async def list_users(email: str=None, first_name: str=None, last_name: str=None, token: str = Depends(jwt_dependency)):
    stub = await get_user_stub()
    req = users_pb2.ListUsersRequest(email=email or '', first_name=first_name or '', last_name=last_name or '')
    try:
        resp = await stub.ListUsers(req, metadata=[('authorization', f'Bearer {token}')])
    except grpc.RpcError as e:
        handle_rpc_error(e, 'ListUsers')
    return list(resp.users)

# Playlist endpoints
@app.post("/listas-reproduccion", status_code=status.HTTP_201_CREATED)
async def create_playlist(request: Request, token: str = Depends(jwt_dependency)):
    payload = await request.json()
    stub = await get_playlist_stub()
    req = playlist_pb2.CreatePlaylistRequest(**payload)
    try:
        resp = await stub.CreatePlaylist(req, metadata=[('authorization', f'Bearer {token}')])
    except grpc.RpcError as e:
        handle_rpc_error(e, 'CreatePlaylist')
    return resp.playlist

@app.get("/listas-reproduccion")
async def list_playlists(token: str = Depends(jwt_dependency)):
    stub = await get_playlist_stub()
    try:
        resp = await stub.ListPlaylists(playlist_pb2.ListPlaylistsRequest(), metadata=[('authorization', f'Bearer {token}')])
    except grpc.RpcError as e:
        handle_rpc_error(e, 'ListPlaylists')
    return list(resp.playlists)

@app.get("/listas-reproduccion/{playlist_id}/videos")
async def get_playlist_videos(playlist_id: str, token: str = Depends(jwt_dependency)):
    stub = await get_playlist_stub()
    try:
        resp = await stub.ListVideos(playlist_pb2.ListVideosRequest(playlist_id=playlist_id), metadata=[('authorization', f'Bearer {token}')])
    except grpc.RpcError as e:
        handle_rpc_error(e, 'ListVideos')
    return list(resp.videos)

@app.post("/listas-reproduccion/{playlist_id}/videos")
async def add_video(playlist_id: str, request: Request, token: str = Depends(jwt_dependency)):
    payload = await request.json()
    stub = await get_playlist_stub()
    req = playlist_pb2.AddVideoRequest(playlist_id=playlist_id, video_id=payload.get('video_id',''))
    try:
        resp = await stub.AddVideo(req, metadata=[('authorization', f'Bearer {token}')])
    except grpc.RpcError as e:
        handle_rpc_error(e, 'AddVideo')
    return resp.playlist

@app.delete("/listas-reproduccion/{playlist_id}/videos", status_code=status.HTTP_204_NO_CONTENT)
async def remove_video(playlist_id: str, request: Request, token: str = Depends(jwt_dependency)):
    payload = await request.json()
    stub = await get_playlist_stub()
    try:
        await stub.RemoveVideo(playlist_pb2.RemoveVideoRequest(playlist_id=playlist_id, video_id=payload.get('video_id','')), metadata=[('authorization', f'Bearer {token}')])
    except grpc.RpcError as e:
        handle_rpc_error(e, 'RemoveVideo')
    return None

@app.delete("/listas-reproduccion/{playlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_playlist(playlist_id: str, token: str = Depends(jwt_dependency)):
    stub = await get_playlist_stub()
    try:
        await stub.DeletePlaylist(playlist_pb2.DeletePlaylistRequest(id=playlist_id), metadata=[('authorization', f'Bearer {token}')])
    except grpc.RpcError as e:
        handle_rpc_error(e, 'DeletePlaylist')
    return None

# Billing endpoints
"""
@app.post("/facturas", status_code=status.HTTP_201_CREATED)
async def create_invoice(request: Request, token: str = Depends(jwt_dependency)):
    payload = await request.json()
    stub = await get_billing_stub()
    req = billing_pb2.CreateInvoiceRequest(**payload)
    try:
        resp = await stub.CreateInvoice(req, metadata=[('authorization', f'Bearer {token}')])
    except grpc.RpcError as e:
        handle_rpc_error(e, 'CreateInvoice')
    await publish_event('billing', 'invoice.created', {'id': resp.invoice.id})
    return resp.invoice

@app.get("/facturas")
async def list_invoices(token: str = Depends(jwt_dependency)):
    stub = await get_billing_stub()
    try:
        resp = await stub.ListInvoices(billing_pb2.ListInvoicesRequest(user_token=token), metadata=[('authorization', f'Bearer {token}')])
    except grpc.RpcError as e:
        handle_rpc_error(e, 'ListInvoices')
    return list(resp.invoices)

@app.get("/facturas/{invoice_id}")
async def get_invoice(invoice_id: str, token: str = Depends(jwt_dependency)):
    stub = await get_billing_stub()
    try:
        resp = await stub.GetInvoice(billing_pb2.GetInvoiceRequest(id=invoice_id), metadata=[('authorization', f'Bearer {token}')])
    except grpc.RpcError as e:
        handle_rpc_error(e, 'GetInvoice')
    return resp.invoice

@app.patch("/facturas/{invoice_id}")
async def update_invoice(invoice_id: str, request: Request, token: str = Depends(jwt_dependency)):
    payload = await request.json()
    stub = await get_billing_stub()
    req = billing_pb2.UpdateInvoiceRequest(id=invoice_id, **payload)
    try:
        resp = await stub.UpdateInvoice(req, metadata=[('authorization', f'Bearer {token}')])
    except grpc.RpcError as e:
        handle_rpc_error(e, 'UpdateInvoice')
    await publish_event('billing', 'invoice.updated', {'id': invoice_id})
    return resp.invoice

@app.delete("/facturas/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invoice(invoice_id: str, token: str = Depends(jwt_dependency)):
    stub = await get_billing_stub()
    try:
        await stub.DeleteInvoice(billing_pb2.DeleteInvoiceRequest(id=invoice_id), metadata=[('authorization', f'Bearer {token}')])
    except grpc.RpcError as e:
        handle_rpc_error(e, 'DeleteInvoice')
    await publish_event('billing', 'invoice.deleted', {'id': invoice_id})
    return None
"""
# Video endpoints
"""
@app.post("/videos", status_code=status.HTTP_201.CREATED)
async def upload_video(request: Request, token: str = Depends(jwt_dependency)):
    payload = await request.json()
    stub = await get_videos_stub()
    req = videos_pb2.UploadVideoRequest(**payload)
    try:
        resp = await stub.UploadVideo(req, metadata=[('authorization', f'Bearer {token}')])
    except grpc.RpcError as e:
        handle_rpc_error(e, 'UploadVideo')
    return resp.video

@app.get("/videos/{video_id}")
async def get_video(video_id: str, token: str = Depends(jwt_dependency)):
    stub = await get_videos_stub()
    try:
        resp = await stub.GetVideo(videos_pb2.GetVideoRequest(id=video_id), metadata=[('authorization', f'Bearer {token}')])
    except grpc.RpcError as e:
        handle_rpc_error(e, 'GetVideo')
    return resp.video

@app.get("/videos")
async def list_videos(token: str = Depends(jwt_dependency)):
    stub = await get_videos_stub()
    try:
        resp = await stub.ListVideos(videos_pb2.ListVideosRequest(), metadata=[('authorization', f'Bearer {token}')])
    except grpc.RpcError as e:
        handle_rpc_error(e, 'ListVideos')
    return list(resp.videos)

@app.patch("/videos/{video_id}")
async def update_video(video_id: str, request: Request, token: str = Depends(jwt_dependency)):
    payload = await request.json()
    stub = await get_videos_stub()
    req = videos_pb2.UpdateVideoRequest(id=video_id, **payload)
    try:
        resp = await stub.UpdateVideo(req, metadata=[('authorization', f'Bearer {token}')])
    except grpc.RpcError as e:
        handle_rpc_error(e, 'UpdateVideo')
    await publish_event('videos', 'video.updated', {'id': video_id})
    return resp.video

@app.delete("/videos/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video(video_id: str, token: str = Depends(jwt_dependency)):
    stub = await get_videos_stub()
    try:
        await stub.DeleteVideo(videos_pb2.DeleteVideoRequest(id=video_id), metadata=[('authorization', f'Bearer {token}')])
    except grpc.RpcError as e:
        handle_rpc_error(e, 'DeleteVideo')
    await publish_event('videos', 'video.deleted', {'id': video_id})
    return None

# Monitoring endpoints
@app.get("/monitoreo/acciones")
async def list_actions(token: str = Depends(jwt_dependency)):
    stub = await get_monitor_stub()
    try:
        resp = await stub.ListActions(monitor_pb2.ListActionsRequest(), metadata=[('authorization', f'Bearer {token}')])
    except grpc.RpcError as e:
        handle_rpc_error(e, 'ListActions')
"""

# Entry point
if __name__ == '__main__':
    import uvicorn
    uvicorn.run('main:app', host='0.0.0.0', port=int(os.getenv('PORT', 8000)), log_level='info')