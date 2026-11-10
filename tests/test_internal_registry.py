"""Read-only internal registry API; uses the existing registry, never a copy."""
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from portal.app import create_app

TOKEN = "registry-test-only-" + "x" * 32


@pytest.fixture
def internal(env, tmp_path):
    token_file = tmp_path / "registry-token"
    token_file.write_text(TOKEN)
    app = create_app(env / "gateway.dev.yml", registry_token_file=token_file)
    with TestClient(app, follow_redirects=False) as client:
        yield client, app.state.portal.registry


def test_disabled_by_default(env, monkeypatch):
    monkeypatch.delenv("PORTAL_REGISTRY_SERVICE_TOKEN_FILE", raising=False)
    with TestClient(create_app(env / "gateway.dev.yml")) as client:
        assert client.get("/internal/apps/noten/access", headers={"Authorization": "Bearer " + TOKEN}).status_code == 404


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer wrong"},
                                    {"X-Portal-Assertion": TOKEN}, {"Cookie": "portal_sid=" + TOKEN},
                                    {"Authorization": "Basic " + TOKEN}])
def test_only_separate_service_credential_accepted(internal, headers):
    response = internal[0].get("/internal/apps/noten/access", headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert TOKEN not in response.text


def test_duplicate_authorization_is_rejected(internal):
    response = internal[0].get("/internal/apps/noten/access",
                               headers=[("Authorization", "Bearer " + TOKEN), ("Authorization", "Bearer " + TOKEN)])
    assert response.status_code == 401


def test_snapshot_contract_and_unknown_app(internal):
    client, registry = internal
    headers = {"Authorization": "Bearer " + TOKEN}
    response = client.get("/internal/apps/noten/access", headers=headers)
    app = registry.snapshot().get("noten")
    assert response.status_code == 200
    assert response.json() == {"slug": app.slug, "roles": sorted(app.roles), "status": app.status,
                               "adapters": list(app.adapters)}
    assert response.headers["cache-control"] == "no-store"
    assert client.get("/internal/apps/unknown-app/access", headers=headers).status_code == 404


def test_latest_existing_snapshot_is_used(internal, env):
    client, registry = internal
    headers = {"Authorization": "Bearer " + TOKEN}
    assert client.get("/internal/apps/noten/access", headers=headers).json()["roles"] == ["student"]
    path = env / "manifests/noten.json"
    manifest = json.loads(path.read_text())
    manifest["roles"] = ["employee"]
    path.write_text(json.dumps(manifest))
    registry.reload()
    assert client.get("/internal/apps/noten/access", headers=headers).json()["roles"] == ["employee"]
    app = registry.snapshot().get("noten")
    registry.set_status(app, "unhealthy", None)
    assert client.get("/internal/apps/noten/access", headers=headers).json()["status"] == "unhealthy"


def test_weak_token_fails_startup(env, tmp_path):
    path = tmp_path / "token"
    path.write_text("weak")
    with pytest.raises(ValueError, match="Registry service token"):
        create_app(env / "gateway.dev.yml", registry_token_file=path)


def test_nginx_public_internal_paths_are_blocked():
    nginx = (Path(__file__).resolve().parents[1] / "extras/compose/vm/nginx-portal.conf").read_text()
    assert "location = /internal { return 404; }" in nginx
    assert "location ^~ /internal/ { return 404; }" in nginx
