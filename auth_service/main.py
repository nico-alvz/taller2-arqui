import os
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from jose import jwt
from sqlalchemy.orm import Session
from passlib.hash import bcrypt

from auth_service.users_models import User, RoleEnum
auth_scheme = HTTPBearer()

class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
    db: Session = Depends(get_user_db),
):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        raise HTTPException(status_code=401, detail="invalid token")
    if db.query(BlacklistedToken).filter_by(token=token).first():
        raise HTTPException(status_code=401, detail="invalid token")
    user = db.get(User, payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="user deleted")
    return token, user


@app.patch("/auth/usuarios/{user_id}")
def update_password(
    user_id: str,
    data: PasswordUpdate,
    auth: tuple = Depends(get_current_user),
    db: Session = Depends(get_user_db),
):
    token, current_user = auth
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="not found")
    if current_user.id != user_id and current_user.role != RoleEnum.admin:
        raise HTTPException(status_code=403, detail="forbidden")
    if current_user.role != RoleEnum.admin:
        if not bcrypt.verify(data.current_password, target.password_hash):
            raise HTTPException(status_code=400, detail="invalid password")
    if data.new_password != data.confirm_password:
        raise HTTPException(status_code=400, detail="passwords do not match")
    target.password_hash = bcrypt.hash(data.new_password)
    db.commit()
    return {
        "id": target.id,
        "email": target.email,
        "full_name": target.full_name,
        "role": target.role,
    }

from auth_service.models import BlacklistedToken
from auth_service.users_db import SessionLocal as UsersSession, Base as UsersBase, engine as users_engine
from auth_service.users_models import User
import pika
import threading
import json

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AuthService")


def _start_user_sync():
    amqp_url = os.getenv("AMQP_URL")
    if not amqp_url:
        return

    def consume():
        try:
            params = pika.URLParameters(amqp_url)
            conn = pika.BlockingConnection(params)
            ch = conn.channel()
            ch.exchange_declare(exchange="users", exchange_type="fanout")
            q = ch.queue_declare(queue="", exclusive=True)
            ch.queue_bind(exchange="users", queue=q.method.queue)
            for method, props, body in ch.consume(q.method.queue, inactivity_timeout=1):
                if method is None:
                    continue
                data = json.loads(body)
                db = SessionLocal()
                user = db.get(User, data["id"])
                if user:
                    user.email = data["email"]
                    user.full_name = data.get("full_name")
                else:
                    db.add(User(id=data["id"], email=data["email"], full_name=data.get("full_name"), password_hash=data.get("password_hash", "")))
                db.commit()
                db.close()
                ch.basic_ack(method.delivery_tag)
        except Exception as e:
            print("user sync error", e)

    threading.Thread(target=consume, daemon=True).start()


_start_user_sync()

SECRET_KEY = os.getenv("JWT_SECRET", "secret")
ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 60

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenRequest(BaseModel):
    token: str

def get_user_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_token_db():
    db = SessionLocal()
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
