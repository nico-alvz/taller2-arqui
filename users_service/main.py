from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from passlib.hash import bcrypt

from db import SessionLocal, engine, Base
import models

Base.metadata.create_all(bind=engine)

app = FastAPI(title="UsersService")

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None
    role: models.RoleEnum = models.RoleEnum.free

class UserRead(BaseModel):
    id: str
    email: EmailStr
    full_name: str | None = None
    role: models.RoleEnum

    class Config:
        orm_mode = True

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/usuarios", response_model=UserRead)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = models.User(email=user.email,
                          password_hash=bcrypt.hash(user.password),
                          full_name=user.full_name,
                          role=user.role)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.get("/usuarios/{user_id}", response_model=UserRead)
def get_user(user_id: str, db: Session = Depends(get_db)):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="not found")
    return user

@app.get("/healthz")
def healthz():
    return {"status": "ok"}
