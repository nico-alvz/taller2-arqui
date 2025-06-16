import os
import grpc
import httpx
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from gen import users_pb2, users_pb2_grpc
from playlist_gen import playlist_pb2, playlist_pb2_grpc  # stubs generados para PlaylistService

# Configuración de URLs y puertos
AUTH_URL = os.getenv('AUTH_SERVICE_URL', 'http://authservice:8000')
USER_GRPC = os.getenv('USER_SERVICE_ADDR', 'userservice:50051')
PLAYLIST_GRPC = os.getenv('PLAYLIST_SERVICE_ADDR', 'playlistservice:50052')
EMAIL_URL = os.getenv('EMAIL_SERVICE_URL', 'http://emailservice:8001')

app = FastAPI(title='API Gateway')
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{AUTH_URL}/auth/login")

# Dependencia para extraer y validar JWT en Gateway (opcionalmente verificar revocación)
async def get_token(token: str = Depends(oauth2_scheme)) -> str:
    return token

# ----- AuthService Endpoints (HTTP proxy) -----
@app.post('/auth/login')
async def login(request: Request):
    async with httpx.AsyncClient() as client:
        resp = await client.post(f'{AUTH_URL}/auth/login', json=await request.json())
    resp.raise_for_status()
    return resp.json()

@app.post('/auth/logout')
async def logout(request: Request, token: str = Depends(get_token)):
    payload = {'token': token}
    async with httpx.AsyncClient() as client:
        resp = await client.post(f'{AUTH_URL}/auth/logout', json=payload)
    resp.raise_for_status()
    return resp.json()

@app.patch('/auth/usuarios/{user_id}')
async def change_password(user_id: str, request: Request, token: str = Depends(get_token)):
    data = await request.json()
    async with httpx.AsyncClient() as client:
        resp = await client.patch(
            f'{AUTH_URL}/auth/usuarios/{user_id}',
            headers={'Authorization': f'Bearer {token}'},
            json=data
        )
    resp.raise_for_status()
    return resp.json()

# ----- UserService Endpoints (gRPC proxy) -----
async def get_user_stub():
    channel = grpc.aio.insecure_channel(USER_GRPC)
    return users_pb2_grpc.UserServiceStub(channel)

@app.post('/users')
async def create_user(request: Request):
    body = await request.json()
    stub = await get_user_stub()
    req = users_pb2.CreateUserRequest(**body)
    resp = await stub.CreateUser(req)
    return resp.user

@app.get('/users/{user_id}')
async def get_user(user_id: str, token: str = Depends(get_token)):
    stub = await get_user_stub()
    req = users_pb2.GetUserByIdRequest(id=user_id)
    metadata = [('authorization', f'Bearer {token}')]
    resp = await stub.GetUserById(req, metadata=metadata)
    return resp.user

@app.patch('/users/{user_id}')
async def update_user(user_id: str, request: Request, token: str = Depends(get_token)):
    body = await request.json()
    stub = await get_user_stub()
    req = users_pb2.UpdateUserRequest(id=user_id, **body)
    metadata = [('authorization', f'Bearer {token}')]
    resp = await stub.UpdateUser(req, metadata=metadata)
    return resp.user

@app.delete('/users/{user_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: str, token: str = Depends(get_token)):
    stub = await get_user_stub()
    req = users_pb2.DeleteUserRequest(id=user_id)
    metadata = [('authorization', f'Bearer {token}')]
    await stub.DeleteUser(req, metadata=metadata)

@app.get('/users')
async def list_users(email: str = '', name: str = '', token: str = Depends(get_token)):
    stub = await get_user_stub()
    req = users_pb2.ListUsersRequest(email=email, name=name)
    metadata = [('authorization', f'Bearer {token}')]
    resp = await stub.ListUsers(req, metadata=metadata)
    return [u for u in resp.users]

# ----- PlaylistService Endpoints (gRPC proxy) -----
async def get_playlist_stub():
    channel = grpc.aio.insecure_channel(PLAYLIST_GRPC)
    return playlist_pb2_grpc.PlaylistServiceStub(channel)

@app.post('/playlists')
async def create_playlist(request: Request, token: str = Depends(get_token)):
    body = await request.json()
    stub = await get_playlist_stub()
    req = playlist_pb2.CreatePlaylistRequest(**body)
    metadata = [('authorization', f'Bearer {token}')]
    resp = await stub.CreatePlaylist(req, metadata=metadata)
    return resp.playlist

# (Define GET, PATCH, DELETE, LIST para playlists de forma similar)

# ----- EmailService Endpoints (gRPC proxy) -----
# Ajustar variable para gRPC
EMAIL_GRPC = os.getenv('EMAIL_SERVICE_ADDR', 'emailservice:50053')

async def get_email_stub():
    channel = grpc.aio.insecure_channel(EMAIL_GRPC)
    return email_pb2_grpc.EmailServiceStub(channel)

@app.post('/email/send')
async def send_email(request: Request, token: str = Depends(get_token)):
    body = await request.json()
    stub = await get_email_stub()
    req = email_pb2.SendEmailRequest(**body)
    metadata = [('authorization', f'Bearer {token}')]
    resp = await stub.SendEmail(req, metadata=metadata)
    return resp

@app.get('/email/status/{message_id}')
async def email_status(message_id: str, token: str = Depends(get_token)):
    stub = await get_email_stub()
    req = email_pb2.GetStatusRequest(message_id=message_id)
    metadata = [('authorization', f'Bearer {token}')]
    resp = await stub.GetStatus(req, metadata=metadata)
    return {'status': resp.status}

# Ejecutar Gateway
if __name__ == '__main__':
    import uvicorn
    uvicorn.run('main:app', host='0.0.0.0', port=8080, reload=True)