from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="UsersService")

class User(BaseModel):
    id: int | None = None
    email: str
    full_name: str | None = None

fake_db = {}

@app.post("/usuarios", response_model=User)
def create_user(user: User):
    user.id = len(fake_db) + 1
    fake_db[user.id] = user
    return user

@app.get("/usuarios/{user_id}", response_model=User)
def get_user(user_id: int):
    user = fake_db.get(user_id)
    if not user:
        return {"detail": "not found"}
    return user

@app.get("/healthz")
def healthz():
    return {"status": "ok"}
