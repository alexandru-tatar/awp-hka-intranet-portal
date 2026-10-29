from fastapi.testclient import TestClient

from src.app.main import app


def test_healthz():
    res = TestClient(app).get("/healthz")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
