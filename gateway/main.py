from fastapi import FastAPI, Request
import httpx

app = FastAPI(title="APIGateway")

SERVICES = {
    'auth': 'http://auth_service:8000',
    'users': 'http://users_service:8001',
    'playlists': 'http://playlist_service:8002',
    'email': 'http://email_service:8003'
}

@app.api_route('/{service}/{path:path}', methods=['GET','POST','PUT','DELETE','PATCH'])
async def proxy(service: str, path: str, request: Request):
    if service not in SERVICES:
        return {'detail': 'service not found'}
    async with httpx.AsyncClient() as client:
        url = f"{SERVICES[service]}/{path}"
        resp = await client.request(request.method, url, json=await request.json() if request.method != 'GET' else None)
        return resp.json()

@app.get('/healthz')
async def healthz():
    return {'status': 'ok'}
