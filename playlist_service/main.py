from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .db import SessionLocal, engine, Base
from . import models

Base.metadata.create_all(bind=engine)

app = FastAPI(title="PlaylistService")


class PlaylistIn(BaseModel):
    user_id: str
    name: str


class PlaylistOut(BaseModel):
    id: int
    user_id: str
    name: str

    class Config:
        orm_mode = True


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/playlists", response_model=PlaylistOut)
def create_playlist(pl: PlaylistIn, db: Session = Depends(get_db)):
    obj = models.Playlist(user_id=pl.user_id, name=pl.name)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@app.get("/playlists/{pl_id}", response_model=PlaylistOut)
def get_playlist(pl_id: int, db: Session = Depends(get_db)):
    pl = db.get(models.Playlist, pl_id)
    if not pl:
        raise HTTPException(status_code=404, detail="not found")
    return pl

@app.get("/healthz")
def healthz():
    return {"status": "ok"}
