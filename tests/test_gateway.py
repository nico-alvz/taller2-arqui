import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from gateway.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_healthz():
    r = client.get('/healthz')
    assert r.status_code == 200
