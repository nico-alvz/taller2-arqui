from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from jose import jwt

app = FastAPI(title="AuthService")

SECRET_KEY = "secret"
ALGORITHM = "HS256"

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/auth/login")
def login(data: LoginRequest):
    # dummy auth
    token = jwt.encode({"sub": data.username}, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token}

@app.post("/auth/logout")
def logout():
    return {"detail": "logged out"}

@app.get("/healthz")
def healthz():
    return {"status": "ok"}
