from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="PlaylistService")

class Playlist(BaseModel):
    id: int | None = None
    user_id: int
    name: str

fake_db = {}

@app.post("/playlists", response_model=Playlist)
def create_playlist(pl: Playlist):
    pl.id = len(fake_db) + 1
    fake_db[pl.id] = pl
    return pl

@app.get("/playlists/{pl_id}", response_model=Playlist)
def get_playlist(pl_id: int):
    return fake_db.get(pl_id)

@app.get("/healthz")
def healthz():
    return {"status": "ok"}
