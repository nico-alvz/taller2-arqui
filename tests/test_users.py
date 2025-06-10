import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from users_service.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_healthz():
    res = client.get('/healthz')
    assert res.status_code == 200
    assert res.json()['status'] == 'ok'
