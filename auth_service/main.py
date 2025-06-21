# auth_service/main.py

import os
import threading
import json
from datetime import datetime, timedelta

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr
from jose import JWTError, jwt
from passlib.hash import bcrypt
import pika
from sqlalchemy.orm import Session

from auth_service.users_db import SessionLocal, Base, engine
from auth_service.users_models import User, RoleEnum
from auth_service.models import BlacklistedToken

# --- Database setup ---
Base.metadata.create_all(bind=engine)

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

# --- RabbitMQ consumer to sync users ---
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
                    user.role = RoleEnum(data.get("role", user.role))
                else:
                    db.add(User(
                        id=data["id"],
                        email=data["email"],
                        full_name=data.get("full_name"),
                        password_hash=data.get("password_hash", ""),
                        role=RoleEnum(data.get("role", RoleEnum.free))
                    ))
                db.commit()
                db.close()
                ch.basic_ack(method.delivery_tag)
        except Exception as e:
            print("user sync error", e)

    threading.Thread(target=consume, daemon=True).start()

_start_user_sync()

# --- JWT & security setup ---
SECRET_KEY = os.getenv("JWT_SECRET", "secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme),
                     user_db: Session = Depends(get_user_db),
                     token_db: Session = Depends(get_token_db)) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise JWTError()
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    # Check blacklist
    if token_db.query(BlacklistedToken).filter_by(token=token).first():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")

    user = user_db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

# --- Pydantic schemas ---
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class PasswordUpdateRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str

class TokenRequest(BaseModel):
    token: str

app = FastAPI(title="AuthService")

# --- Endpoints ---
@app.post("/auth/login")
def login(data: LoginRequest, db: Session = Depends(get_user_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not bcrypt.verify(data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token = jwt.encode({"sub": user.id, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "created_at": user.created_at,
            "updated_at": user.updated_at
        }
    }

@app.patch("/auth/usuarios/{user_id}")
def update_password(user_id: str,
                    data: PasswordUpdateRequest,
                    current_user: User = Depends(get_current_user),
                    db: Session = Depends(get_user_db)):
    # Authorization: client only self, admin any
    if current_user.role != RoleEnum.admin and current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted")

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not bcrypt.verify(data.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password incorrect")
    if data.new_password != data.confirm_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match")

    user.password_hash = bcrypt.hash(data.new_password)
    db.commit()
    return {"detail": "Password updated successfully"}

@app.post("/auth/logout")
def logout(payload: TokenRequest, db: Session = Depends(get_token_db)):
    try:
        decoded = jwt.decode(payload.token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    db.add(BlacklistedToken(
        token=payload.token,
        user_id=decoded["sub"],
        expires_at=datetime.utcfromtimestamp(decoded["exp"])
    ))
    db.commit()
    return {"detail": "Logged out"}

@app.get("/healthz")
def healthz():
    return {"status": "ok"}
