"""Fehler-Standard: Arten, 504 ohne type, Standardbehandlung nicht abgefangener Fehler (sdk/README.md)."""

import json
import logging

import httpx
import pytest
from conftest import make_portal, make_token
from fastapi import Depends, FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
from platform_sdk import AdapterError, User
from platform_sdk.adapters import transport
from platform_sdk.adapters.bwsync import errors


def test_arten():
    assert transport.category(AdapterError(503, transport.BACKEND_UNAVAILABLE, "")) == "technical"
    assert transport.category(AdapterError(504, transport.BACKEND_TIMEOUT, "")) == "technical"
    assert transport.category(AdapterError(502, transport.CONTRACT_VIOLATION, "")) == "technical"
    for kind in (transport.NO_USER_CONTEXT, transport.NOT_IMPLEMENTED, transport.DOWNLOAD_TOO_LARGE,
                 transport.SCOPE_NOT_GRANTED):
        assert transport.category(AdapterError(500, kind, "")) == "call"
    assert transport.category(AdapterError(423, errors.LOCKED, "")) == "domain"
    assert transport.category(AdapterError(409, "unbekannt-neu", "")) == "domain"  # unbekannt: fachlich


@pytest.mark.parametrize("status,body,kind", [
    (504, b"", transport.BACKEND_TIMEOUT),
    (502, b"", transport.BACKEND_UNAVAILABLE),
    (400, b'{"detail": "x"}', transport.BACKEND_UNAVAILABLE),
    (500, b"[1, 2]", transport.BACKEND_UNAVAILABLE),  # JSON, aber kein Objekt
    (504, b'{"type": "urn:hka:problem:bwsync-locked"}', errors.LOCKED),  # eigener type gewinnt
])
def test_antwort_ohne_type(status, body, kind):
    err = transport._problem(httpx.Response(status, content=body))
    assert (err.status, err.type) == (status, kind)


class Lines(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines = []

    def emit(self, record):
        self.lines.append(json.loads(record.getMessage()))


@pytest.fixture
def log_lines():
    handler = Lines()
    logger = logging.getLogger("platform_sdk.errors")
    logger.addHandler(handler)
    yield handler.lines
    logger.removeHandler(handler)


def make_app() -> FastAPI:
    portal = make_portal()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    portal.install(app)
    router = portal.router()
    errors_by_path = {
        "fachlich": AdapterError(423, errors.LOCKED, "geheimes detail"),
        "technisch": AdapterError(503, transport.BACKEND_UNAVAILABLE, ""),
        "zeit": AdapterError(504, transport.BACKEND_TIMEOUT, ""),
        "aufruf": AdapterError(500, transport.NO_USER_CONTEXT, "geheimes detail"),
        "recht": AdapterError(403, transport.SCOPE_NOT_GRANTED, "geheimes detail"),
    }

    @router.get("/fehler/{art}")
    async def fehler(art: str, user: User = Depends(portal.user)) -> dict:
        if art == "anderer":
            raise RuntimeError("geheimer Text aus dem Stack")
        raise errors_by_path[art]

    @router.get("/abgefangen", response_class=HTMLResponse)
    async def abgefangen(user: User = Depends(portal.user)) -> str:
        try:
            raise errors_by_path["fachlich"]
        except AdapterError:
            return "<h1>Eigener Text der App</h1>"

    app.include_router(router)
    return app


@pytest.fixture
def client():
    return TestClient(make_app(), raise_server_exceptions=False)


def get(client, path, accept="text/html"):
    return client.get(path, headers={"X-Portal-Assertion": make_token(), "X-Request-Id": "req-123", "Accept": accept})


@pytest.mark.parametrize("art,status,title,text", [
    ("fachlich", 423, "Das hat nicht geklappt", "Die Aktion war nicht möglich."),
    ("technisch", 503, "Gerade nicht erreichbar", "später erneut"),
    ("zeit", 504, "Gerade nicht erreichbar", "später erneut"),
    ("aufruf", 500, "Fehler in der Anwendung", "nennen Sie bitte die Vorgangsnummer"),
    ("recht", 500, "Fehler in der Anwendung", "nennen Sie bitte die Vorgangsnummer"),
    ("anderer", 500, "Fehler in der Anwendung", "nennen Sie bitte die Vorgangsnummer"),
])
def test_fallback_html(client, log_lines, art, status, title, text):
    response = get(client, f"/fehler/{art}")
    assert response.status_code == status
    html = response.text
    assert '<html lang="de">' in html and f"<h1>{title}</h1>" in html and text in html
    assert "Vorgangsnummer: req-123" in html
    assert "geheim" not in html and "Traceback" not in html and "RuntimeError" not in html
    [line] = log_lines
    assert line["event"] == "unhandled-error" and line["request_id"] == "req-123"
    assert line["level"] == ("warning" if art in ("fachlich", "technisch", "zeit") else "error")


def test_fallback_json_behaelt_type(client):
    response = get(client, "/fehler/fachlich", accept="application/json")
    assert response.status_code == 423 and response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"] == "urn:hka:problem:bwsync-locked" and body["request_id"] == "req-123"
    assert body["title"] == "Das hat nicht geklappt" and "geheim" not in json.dumps(body)


def test_fallback_json_anderer_fehler(client):
    response = get(client, "/fehler/anderer", accept="application/json")
    body = response.json()
    assert response.status_code == 500 and body["type"] == "urn:hka:problem:500"
    assert "geheim" not in response.text and "Traceback" not in response.text


def test_log_details_nur_im_log(client, log_lines):
    get(client, "/fehler/aufruf")
    get(client, "/fehler/anderer")
    get(client, "/fehler/fachlich")
    aufruf, anderer, fachlich = log_lines
    assert aufruf["detail"] == "geheimes detail" and aufruf["type"] == transport.NO_USER_CONTEXT
    assert anderer["category"] == "other" and "geheimer Text aus dem Stack" in anderer["stack"]
    assert "detail" not in fachlich and fachlich["type"] == errors.LOCKED and "hint" in fachlich


def test_app_faengt_selbst_ab(client, log_lines):
    response = get(client, "/abgefangen")
    assert response.status_code == 200 and "Eigener Text der App" in response.text and log_lines == []


def test_portal_fehler_bleiben_wie_bisher(client):
    response = client.get("/fehler/fachlich", headers={"Accept": "text/html"})  # ohne Assertion
    assert response.status_code == 401 and "Anmeldung" in response.text
