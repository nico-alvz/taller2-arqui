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

SERVICES = {
    'auth': 'http://auth_service:8000',
    'users': 'http://users_service:8001',
    'playlists': 'http://playlist_service:8002',
    'email': 'http://email_service:8003',
    'videos': 'http://videos_service:8010',
    'facturas': 'http://billing_service:8011',
    'interacciones': 'http://interacciones_service:8012',
    'monitoreo': 'http://monitoreo_service:8013'
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
        return resp.json()

@app.get('/healthz')
async def healthz():
    return {'status': 'ok'}
