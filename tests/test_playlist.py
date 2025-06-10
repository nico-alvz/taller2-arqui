import os, sys
os.environ['PLAYLIST_DB_URL'] = 'sqlite:///:memory:'

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from playlist_service.db import Base, engine
from playlist_service.main import app

Base.metadata.create_all(bind=engine)

from fastapi.testclient import TestClient
client = TestClient(app)


def test_create_playlist():
    res = client.post('/playlists', json={'user_id': 'u1', 'name': 'My list'})
    assert res.status_code == 200
    pid = res.json()['id']
    out = client.get(f'/playlists/{pid}')
    assert out.status_code == 200
    assert out.json()['name'] == 'My list'


def test_add_video(monkeypatch):
    client.post('/playlists', json={'user_id': 'u2', 'name': 'Videos'})
    # mock video service call
    def mock_get(url):
        class R: status_code = 200
        return R()
    monkeypatch.setattr('httpx.get', mock_get)
    res = client.post('/playlists/1/videos', json={'video_id': 'v1'})
    assert res.status_code == 200
    out = client.get('/playlists/1/videos')
    assert out.json() == ['v1']
