import os
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from jose import jwt
from sqlalchemy.orm import Session
from passlib.hash import bcrypt

from db import SessionLocal as TokenSession, Base as TokenBase, engine as token_engine
from models import BlacklistedToken
from users_db import SessionLocal as UsersSession, Base as UsersBase, engine as users_engine
from users_models import User

TokenBase.metadata.create_all(bind=token_engine)
UsersBase.metadata.create_all(bind=users_engine)

app = FastAPI(title="AuthService")

SECRET_KEY = os.getenv("JWT_SECRET", "secret")
ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 60

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenRequest(BaseModel):
    token: str

def get_user_db():
    db = UsersSession()
    try:
        yield db
    finally:
        db.close()

def get_token_db():
    db = TokenSession()
    try:
        yield db
    finally:
        db.close()

@app.post("/auth/login")
def login(data: LoginRequest, db: Session = Depends(get_user_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not bcrypt.verify(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token = jwt.encode({"sub": user.id, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token}

@app.post("/auth/logout")
def logout(payload: TokenRequest, db: Session = Depends(get_token_db)):
    try:
        decoded = jwt.decode(payload.token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        raise HTTPException(status_code=401, detail="invalid token")
    db.add(BlacklistedToken(token=payload.token, user_id=decoded["sub"], expires_at=datetime.utcfromtimestamp(decoded["exp"])))
    db.commit()
    return {"detail": "logged out"}

@app.get("/healthz")
def healthz():
    return {"status": "ok"}
