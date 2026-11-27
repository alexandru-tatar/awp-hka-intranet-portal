"""Deutsch und Englisch im SDK (HKA-101): Sprache aus Accept-Language, Rahmen, Fehlerseiten, Test-Anmeldung."""

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
    assert "Skip to content" in html and "Logged in as" in html
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
    assert "You do not have permission for this" in r.text and "This app is not available for your role." in r.text
    assert "Dafür fehlt Ihnen die Berechtigung" not in r.text
    assert '<p class="error-page__status">Error 403</p>' in r.text
    # HKA-95: Seite im Seitenrahmen mit Weg zur Startseite, auch auf Englisch
    assert 'class="site-header"' in r.text and '<html lang="en">' in r.text
    assert '<a class="cta" href="/">back to home</a>' in r.text and "zur Startseite" not in r.text


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


def test_ersatz_menue_auf_englisch(client):
    de = client.get("/", headers=student()).text
    en = client.get("/", headers=student(**EN)).text
    assert "Meine Noten" in de and ">Studium<" in de
    assert "My grades" in en and ">Studies<" in en and "Meine Noten" not in en


def test_ersatz_menue_ohne_englische_felder_zeigt_deutsch():
    """Ältere Manifeste ohne label_en: die Beschriftung bleibt Deutsch, auch bei englischer Anfrage."""
    from conftest import MANIFEST, make_portal
    from platform_sdk.context import current_language

    portal = make_portal()
    portal.config.manifest["menu"] = {k: v for k, v in MANIFEST["menu"].items() if k != "label_en"}
    token = current_language.set("en")
    try:
        assert portal._layout._menu_item()["label"] == "Meine Noten"
    finally:
        current_language.reset(token)


def test_test_anmeldung_titel_englisch(dev_client):
    assert "Test login – Grades overview" in dev_client.get("/__dev/login", headers=EN).text


@pytest.mark.parametrize("env, marker", [
    ({"PORTAL_LANG": "en"}, "ERROR PF-103  –  Portal library changed"),
    ({"LANG": "en_US.UTF-8"}, "ERROR PF-103"),
    ({"PORTAL_LANG": "de", "LANG": "en_US.UTF-8"}, "FEHLER PF-103  –  Portal-Bibliothek verändert"),
    ({}, "FEHLER PF-103"),
])
def test_pf103_in_der_sprache_der_umgebung(tmp_path, env, marker):
    """HKA-101: ``python -m platform_sdk.verify_tree`` meldet PF-103 nach PORTAL_LANG bzw. LC_ALL, LC_MESSAGES, LANG."""
    import os
    import shutil
    import subprocess
    import sys
    from pathlib import Path

    source = Path(__file__).resolve().parent.parent / "platform_sdk"
    copy = tmp_path / "platform_sdk"
    shutil.copytree(source, copy, ignore=shutil.ignore_patterns("__pycache__"))
    (copy / "SHA256").write_text("sha256:falsch\n")
    clean = {k: v for k, v in os.environ.items() if k not in ("PORTAL_LANG", "LC_ALL", "LC_MESSAGES", "LANG")}
    result = subprocess.run([sys.executable, "-m", "platform_sdk.verify_tree"], cwd=tmp_path, env={**clean, **env},
                            capture_output=True, text=True)
    assert result.returncode == 1 and marker in result.stderr


@pytest.mark.parametrize("broken", ["texts.json", "i18n.py"])
def test_pf103_auch_wenn_i18n_kaputt_ist(tmp_path, broken):
    """Die Prüfung meldet PF-103 (auf Deutsch), auch wenn i18n.py oder texts.json beschädigt sind."""
    import os
    import shutil
    import subprocess
    import sys
    from pathlib import Path

    source = Path(__file__).resolve().parent.parent / "platform_sdk"
    copy = tmp_path / "platform_sdk"
    shutil.copytree(source, copy, ignore=shutil.ignore_patterns("__pycache__"))
    (copy / broken).write_text("{ kaputt", encoding="utf-8")
    clean = {k: v for k, v in os.environ.items() if k not in ("PORTAL_LANG", "LC_ALL", "LC_MESSAGES", "LANG")}
    result = subprocess.run([sys.executable, "-m", "platform_sdk.verify_tree"], cwd=tmp_path,
                            env={**clean, "PORTAL_LANG": "en"}, capture_output=True, text=True)
    assert result.returncode == 1 and "PF-103" in result.stderr and "Traceback" not in result.stderr
