import os
from fastapi import FastAPI, Request
import httpx
from jose import jwt

app = FastAPI(title="APIGateway")

SECRET_KEY = os.getenv("JWT_SECRET", "secret")


@app.middleware("http")
async def jwt_middleware(request: Request, call_next):
    token = request.headers.get("Authorization")
    if token and token.startswith("Bearer "):
        try:
            payload = jwt.decode(token[7:], SECRET_KEY, algorithms=["HS256"])
            request.state.user_id = payload.get("sub")
        except Exception:
            request.state.user_id = None
    return await call_next(request)

from fastapi import FastAPI, Request
import httpx

app = FastAPI(title="APIGateway")

SERVICES = {
    'auth': 'http://auth_service:8000',
    'users': 'http://users_service:8001',
    'playlists': 'http://playlist_service:8002',
    'email': 'http://email_service:8003',
    'videos': 'http://video_mock:8010',
    'facturas': 'http://billing_mock:8011'
    'email': 'http://email_service:8003'
}

@app.api_route('/{service}/{path:path}', methods=['GET','POST','PUT','DELETE','PATCH'])
async def proxy(service: str, path: str, request: Request):
    if service not in SERVICES:
        return {'detail': 'service not found'}
    async with httpx.AsyncClient() as client:
        url = f"{SERVICES[service]}/{path}"
        data = await request.json() if request.method != 'GET' else None
        headers = {}
        if request.headers.get('Authorization'):
            headers['Authorization'] = request.headers['Authorization']
        resp = await client.request(request.method, url, json=data, headers=headers)
        resp = await client.request(request.method, url, json=await request.json() if request.method != 'GET' else None)
        return resp.json()

@app.get('/healthz')
async def healthz():
    return {'status': 'ok'}
