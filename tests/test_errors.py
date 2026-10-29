"""Fehlerseiten: jeder übliche Status erscheint als HTML-Seite des Portals, nie als JSON."""

import pytest
import yaml
from fastapi.testclient import TestClient

from conftest import ROOT
from portal.app import create_app

MESSAGES = yaml.safe_load((ROOT / "src" / "portal" / "locales" / "messages.de.yml").read_text(encoding="utf-8"))

SPECIFIC = [400, 401, 403, 404, 405, 408, 409, 410, 413, 414, 415, 422, 429, 501, 502, 503, 504]
FALLBACK = {418: "4xx", 451: "4xx", 500: "5xx", 507: "5xx", 599: "5xx"}


def assert_html_error_page(r, status, title):
    assert r.status_code == status
    assert r.headers["content-type"].startswith("text/html")
    assert f"<h1>{title}</h1>" in r.text
    assert "Fehlernummer" in r.text and 'href="/">' in r.text
    assert not r.text.lstrip().startswith("{")


@pytest.mark.parametrize("status", SPECIFIC)
def test_every_common_status_has_its_own_html_page(client, status):
    r = client.get(f"/_portal/error/{status}", headers={"X-Request-Id": "abc-123"})
    assert_html_error_page(r, status, MESSAGES[f"error.{status}.title"])
    assert "abc-123" in r.text


@pytest.mark.parametrize("status,key", FALLBACK.items())
def test_other_statuses_fall_back_to_a_generic_page(client, status, key):
    assert_html_error_page(client.get(f"/_portal/error/{status}"), status, MESSAGES[f"error.{key}.title"])


def test_out_of_range_status_is_404(client):
    assert client.get("/_portal/error/200").status_code == 404


def test_401_page_links_to_login(client):
    assert 'href="/login"' in client.get("/_portal/error/401").text
    assert 'href="/login"' not in client.get("/_portal/error/404").text


def test_unknown_path_is_404_page(client):
    assert_html_error_page(client.get("/gibt/es/nicht"), 404, MESSAGES["error.404.title"])


def test_wrong_method_is_405_page_with_allow_header(client):
    r = client.post("/_portal/status")
    assert_html_error_page(r, 405, MESSAGES["error.405.title"])
    assert "GET" in r.headers["allow"]


def test_invalid_input_is_422_page_not_json(client):
    assert_html_error_page(client.get("/_portal/error/abc"), 422, MESSAGES["error.422.title"])


def test_forbidden_for_signed_in_user_is_403_page(client):
    from conftest import login
    login(client, "alexandru")
    assert_html_error_page(client.get("/_portal/status"), 403, MESSAGES["error.403.title"])


def test_unhandled_exception_is_500_page_with_request_id(env, monkeypatch):
    app = create_app(env / "gateway.dev.yml")
    portal = app.state.portal

    def boom(*args, **kwargs):
        raise RuntimeError("kaputt")

    monkeypatch.setattr(portal.app_service, "find_all", boom)
    client = TestClient(app, raise_server_exceptions=False, follow_redirects=False)
    from conftest import login
    login(client, "admin")
    r = client.get("/_portal/status", headers={"X-Request-Id": "req-500"})
    assert_html_error_page(r, 500, MESSAGES["error.5xx.title"])
    assert "req-500" in r.text and "kaputt" not in r.text


def test_static_files_keep_a_bare_status(client):
    r = client.get("/_portal/static/gibt-es-nicht.css")
    assert r.status_code == 404 and r.text == ""
