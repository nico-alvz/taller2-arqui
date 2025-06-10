from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import httpx

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


class VideoIn(BaseModel):
    video_id: str


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


@app.get("/playlists")
def list_playlists(db: Session = Depends(get_db)):
    return db.query(models.Playlist).all()


@app.post("/playlists/{pl_id}/videos")
def add_video(pl_id: int, data: VideoIn, db: Session = Depends(get_db)):
    pl = db.get(models.Playlist, pl_id)
    if not pl:
        raise HTTPException(status_code=404, detail="playlist not found")
    # verify video exists via stub
    try:
        r = httpx.get(f"http://video_mock:8010/videos/{data.video_id}")
        if r.status_code != 200:
            raise Exception
    except Exception:
        raise HTTPException(status_code=400, detail="invalid video")
    pv = models.PlaylistVideo(playlist_id=pl_id, video_id=data.video_id)
    db.add(pv)
    db.commit()
    return {"detail": "added"}


@app.get("/playlists/{pl_id}/videos")
def list_videos(pl_id: int, db: Session = Depends(get_db)):
    rows = db.query(models.PlaylistVideo).filter_by(playlist_id=pl_id).all()
    return [r.video_id for r in rows]


@app.get("/playlists/{pl_id}", response_model=PlaylistOut)
def get_playlist(pl_id: int, db: Session = Depends(get_db)):
    pl = db.get(models.Playlist, pl_id)
    if not pl:
        raise HTTPException(status_code=404, detail="not found")
    return pl

@app.get("/healthz")
def healthz():
    return {"status": "ok"}
