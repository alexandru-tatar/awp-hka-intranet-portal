"""Middleware, Rollen, Seitenrahmen, Entwicklungsmodus, Schnittstellen und Prüfsumme (06 §13: S3, S6, S8, S9, S11)."""

import shutil

import httpx
import pytest
from conftest import make_token
from platform_sdk.adapters.transport import FixtureTransport
from platform_sdk.config import DEV_REFUSED, Config
from platform_sdk.errors import AdapterError
from platform_sdk import layout as layout_module
from platform_sdk.verify_tree import tree_hash


def test_healthz_offen(client):
    assert client.get("/healthz").status_code == 200


def test_ohne_assertion_401_html(client):
    response = client.get("/", headers={"Accept": "text/html"})
    assert response.status_code == 401
    assert '<html lang="de">' in response.text


def test_ohne_assertion_401_problem(client):
    response = client.get("/")
    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"


def test_gueltige_assertion_layout(client):
    response = client.get("/", headers={"X-Portal-Assertion": make_token()})
    assert response.status_code == 200
    html = response.text
    assert '<html lang="de">' in html
    assert 'href="#main"' in html
    assert 'aria-label="Hauptnavigation"' in html  # Ersatz-Menü, weil das Portal nicht erreichbar ist
    assert "Erika Musterfrau" in html
    assert "/static/app.css" in html


def test_menue_vom_portal_mit_bearer(client, monkeypatch):
    """S6/S7: `layout()` holt das Menü mit `Authorization: Bearer <Token der Anfrage>` (02 §3), nicht mit `X-Portal-Assertion`."""
    token = make_token()
    seen: list[httpx.Request] = []

    def portal_antwort(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text='<nav aria-label="Hauptnavigation">Menü vom Portal</nav>', headers={"X-Portal-Kit": "kit-abc"})

    real = httpx.AsyncClient
    monkeypatch.setattr(layout_module.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(portal_antwort), **kw))
    response = client.get("/", headers={"X-Portal-Assertion": token})
    assert response.status_code == 200
    assert "Menü vom Portal" in response.text and "/_portal/static/kit-abc.css" in response.text
    assert len(seen) == 1 and seen[0].url.path == "/nav"
    assert seen[0].headers["authorization"] == f"Bearer {token}"
    assert "x-portal-assertion" not in seen[0].headers


def test_requires_403(client):
    response = client.get("/nur-professor", headers={"X-Portal-Assertion": make_token()})
    assert response.status_code == 403


def test_adapter_nicht_erreichbar():
    import asyncio

    from platform_sdk.adapters.transport import HttpTransport
    from platform_sdk.context import current_assertion

    current_assertion.set(make_token())
    with pytest.raises(AdapterError) as exc:
        asyncio.run(HttpTransport("http://127.0.0.1:9").get("/v1/noten/me/grades", None))
    assert exc.value.type == "backend-unavailable"
    assert exc.value.detail == "Das System ist gerade nicht erreichbar."


def test_dev_abgelehnt_in_produktion(monkeypatch):
    monkeypatch.setenv("PORTAL_DEV", "1")
    monkeypatch.setenv("PORTAL_ENV", "production")
    with pytest.raises(RuntimeError, match=DEV_REFUSED):
        Config.from_env("/dev/null")


def test_dev_abgelehnt_mit_base_path(monkeypatch, tmp_path):
    (tmp_path / "manifest.json").write_text('{"slug": "noten"}')
    monkeypatch.setenv("PORTAL_DEV", "1")
    monkeypatch.setenv("PORTAL_BASE_PATH", "/apps/noten")
    with pytest.raises(RuntimeError, match=DEV_REFUSED):
        Config.from_env(str(tmp_path / "manifest.json"))


def test_dev_login(dev_client):
    first = dev_client.get("/", follow_redirects=False)
    assert first.status_code == 303 and first.headers["location"] == "/__dev/login"
    assert dev_client.get("/__dev/login").status_code == 200
    dev_client.post("/__dev/login", data={"sub": "student-test", "roles": "student"}, follow_redirects=False)
    page = dev_client.get("/")
    assert page.status_code == 200
    assert "Entwicklungsmodus – Testperson: Erika Musterfrau" in page.text
    assert dev_client.get("/noten").json() == {"count": 5}
    assert dev_client.get("/nur-professor").status_code == 403


def test_dev_rollen(dev_client):
    dev_client.post("/__dev/login", data={"sub": "student-empty", "extra_roles": "professor"})
    assert dev_client.get("/nur-professor").status_code == 200
    assert dev_client.get("/noten").json() == {"count": 0}


def test_fixture_ohne_person():
    import asyncio

    with pytest.raises(AdapterError) as exc:
        asyncio.run(FixtureTransport().get("/v1/noten/me/grades", None))
    assert exc.value.type == "no-user-context"


def test_pruefsumme(tmp_path):
    from platform_sdk import verify_tree

    tree = tmp_path / "platform_sdk"
    shutil.copytree(verify_tree.ROOT, tree, ignore=shutil.ignore_patterns("__pycache__"))
    before = tree_hash(tree)
    (tree / "VERSION").write_text("9.9.9\n")
    assert tree_hash(tree) != before
    (tree / "VERSION").unlink()
    assert tree_hash(tree) != before
