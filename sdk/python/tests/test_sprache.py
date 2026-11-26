"""Deutsch und Englisch im SDK (HKA-101): Sprache aus Accept-Language, Rahmen, Fehlerseiten, Test-Anmeldung."""

import json
import re
from pathlib import Path

import httpx
import pytest
from conftest import make_token
from platform_sdk import layout as layout_module
from platform_sdk.i18n import LANGUAGES, TEXTS, pick_language

HTML = {"Accept": "text/html"}
EN = {"Accept-Language": "en-GB,en;q=0.9"}


def student(**headers):
    return {"X-Portal-Assertion": make_token(), **headers}


@pytest.mark.parametrize("header, expected", [
    (None, "de"), ("", "de"), ("en", "en"), ("en-GB,en;q=0.9,de;q=0.8", "en"), ("de-DE,de;q=0.9,en;q=0.8", "de"),
    ("fr,en;q=0.5", "en"), ("fr-CH,fr;q=0.9", "de"), ("*", "de"), ("en;q=0", "de"), ("en;q=abc", "de"),
    ("en;q=inf", "de"), ("EN-us", "en"), ("de;q=0.5,en;q=0.9", "en"), ("en," * 200, "de"),
])
def test_pick_language(header, expected):
    assert pick_language(header) == expected


def test_texte_in_beiden_sprachen_gleiche_schluessel():
    assert set(TEXTS) == set(LANGUAGES)
    assert set(TEXTS["de"]) == set(TEXTS["en"])
    assert all(TEXTS["en"][k] for k in TEXTS["en"])


def test_texts_json_in_python_und_javascript_gleich():
    here = Path(__file__).resolve().parent.parent.parent
    assert (here / "python/platform_sdk/texts.json").read_bytes() == (here / "javascript/platform_sdk/texts.json").read_bytes()


def test_rahmen_auf_englisch(client):
    html = client.get("/", headers=student(**EN)).text
    assert '<html lang="en">' in html
    assert "Skip to content" in html and "Signed in as" in html
    assert 'aria-label="Main navigation"' in html and "<summary>Menu</summary>" in html
    assert "Do you want to log out of the portal?" in html and ">Cancel</button>" in html
    assert "Zum Inhalt" not in html and "Abmelden" not in html


def test_rahmen_standard_deutsch(client):
    html = client.get("/", headers=student()).text
    assert '<html lang="de">' in html and "Abmelden" in html and "Skip to content" not in html
    assert '<html lang="de">' in client.get("/", headers=student(**{"Accept-Language": "fr"})).text


def test_ohne_assertion_auf_englisch(client):
    r = client.get("/", headers={**HTML, **EN})
    assert r.status_code == 401
    assert '<html lang="en">' in r.text and "Login missing" in r.text and "log in there" in r.text


def test_ohne_assertion_problem_json_auf_englisch(client):
    r = client.get("/", headers=EN)
    assert r.headers["content-type"] == "application/problem+json"
    assert r.json()["title"] == "Login missing"


def test_kein_zugriff_auf_englisch(client):
    r = client.get("/nur-professor", headers=student(**HTML, **EN))
    assert r.status_code == 403
    assert "No access" in r.text and "This page is not available for your role." in r.text
    assert "Kein Zugriff" not in r.text


def test_menue_anfrage_traegt_sprache(client, monkeypatch):
    seen: list[httpx.Request] = []

    def portal_antwort(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text="<nav>Menü vom Portal</nav>", headers={"X-Portal-Kit": "kit-abc"})

    real = httpx.AsyncClient
    monkeypatch.setattr(layout_module.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(portal_antwort), **kw))
    client.get("/", headers=student(**EN))
    client.get("/", headers=student())
    assert [r.headers["accept-language"] for r in seen] == ["en", "de"]


def test_test_anmeldung_auf_englisch(dev_client):
    r = dev_client.get("/__dev/login", headers=EN)
    assert '<html lang="en">' in r.text and "Test login" in r.text and "Roles from the manifest" in r.text
    assert "Testperson" not in r.text
    de = dev_client.get("/__dev/login").text
    assert '<html lang="de">' in de and "Test-Anmeldung" in de


@pytest.mark.parametrize("header, expected", [(None, "de"), ("en-GB,en;q=0.9", "en"), ("fr", "de"), ("de,en;q=0.5", "de")])
def test_portal_language_fuer_eigene_texte(header, expected):
    """Apps lesen die Sprache mit portal.language(request) (Regel R-UI-7: alle Texte in beiden Sprachen)."""
    from conftest import make_portal
    from starlette.requests import Request

    headers = [(b"accept-language", header.encode())] if header else []
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": headers})
    assert make_portal().language(request) == expected
