"""Deutsch und Englisch (HKA-101): Textdateien, Sprachwahl, Umschalter, Menü und Fehlerseiten."""

import string

import pytest
import yaml

from conftest import ROOT, login
from portal.core.i18n import DEFAULT_LANGUAGE, LANGUAGES, Messages, current_language, pick_language
from portal.auth.redirects import sanitize_local_path

LOCALES = ROOT / "src" / "portal" / "locales"


def load(code: str) -> dict[str, str]:
    return yaml.safe_load((LOCALES / f"messages.{code}.yml").read_text(encoding="utf-8"))


def placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(str(text)) if name}


# ── AK4: gleiche Schlüssel und Platzhalter in allen Sprachen ──────────────────

@pytest.mark.parametrize("code", [c for c in LANGUAGES if c != DEFAULT_LANGUAGE])
def test_same_keys_as_german(code):
    de, other = load(DEFAULT_LANGUAGE), load(code)
    assert sorted(set(de) - set(other)) == [], f"fehlt in messages.{code}.yml"
    assert sorted(set(other) - set(de)) == [], f"nur in messages.{code}.yml"


@pytest.mark.parametrize("code", [c for c in LANGUAGES if c != DEFAULT_LANGUAGE])
def test_same_placeholders_as_german(code):
    de, other = load(DEFAULT_LANGUAGE), load(code)
    different = {k: (placeholders(de[k]), placeholders(other[k])) for k in de if k in other
                 and placeholders(de[k]) != placeholders(other[k])}
    assert different == {}


def test_english_texts_are_translated():
    de, en = load("de"), load("en")
    same = sorted(k for k in de if de[k] == en[k])
    # Eigennamen, Sprachnamen und Zeichen, die in beiden Sprachen gleich sind
    allowed = {"app.title", "brand.name", "brand.sub", "lang.name.de", "lang.name.en", "status.unknown",
               "footer.docs",
               "status.col.version", "status.col.status", "admin.col.version", "admin.col.status", "admin.col.sub",
               "admin.col.person"}
    assert [k for k in same if k not in allowed] == []


# ── Sprache bestimmen ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("cookie, header, expected", [
    (None, None, "de"),
    (None, "", "de"),
    (None, "en", "en"),
    (None, "en-GB,en;q=0.9,de;q=0.8", "en"),
    (None, "de-DE,de;q=0.9,en;q=0.8", "de"),
    (None, "fr,en;q=0.5", "en"),
    (None, "fr-CH,fr;q=0.9", "de"),
    (None, "*", "de"),
    (None, "en;q=0", "de"),
    (None, "en;q=abc", "de"),
    (None, "EN-us", "en"),
    (None, "de;q=0.5,en;q=0.9", "en"),
    ("en", "de", "en"),
    ("de", "en", "de"),
    ("fr", "en", "en"),
    ("", None, "de"),
    (None, "en," * 200, "de"),   # zu lang: ignorieren
])
def test_pick_language(cookie, header, expected):
    assert pick_language(cookie, header) == expected


def test_sanitize_local_path():
    assert sanitize_local_path("/_portal/admin?x=1") == "/_portal/admin?x=1"
    assert sanitize_local_path("/") == "/"
    for bad in (None, "", "https://evil.example", "//evil.example", "/\\evil", "/a\nb", "evil", "/" + "a" * 600):
        assert sanitize_local_path(bad) == "/"


# ── Messages ──────────────────────────────────────────────────────────────────

def test_messages_follow_current_language():
    t = Messages(LOCALES, defaults={"kontakt": "IT"})
    assert t("home.title") == "Startseite"
    token = current_language.set("en")
    try:
        assert t("home.title") == "Home"
        assert t.lang == "en"
        assert t("nav.empty") == "No app is available to you at the moment. If you expect one, contact IT."
    finally:
        current_language.reset(token)


def test_messages_default_can_differ_per_language():
    t = Messages(LOCALES, defaults={"kontakt": {"de": "den Servicedesk", "en": "the service desk"}})
    assert t("nav.empty").endswith("melden Sie sich bei den Servicedesk.")
    token = current_language.set("en")
    try:
        assert t("nav.empty").endswith("contact the service desk.")
    finally:
        current_language.reset(token)


def test_messages_default_without_english_falls_back_to_german():
    t = Messages(LOCALES, defaults={"kontakt": {"de": "den Servicedesk"}})
    token = current_language.set("en")
    try:
        assert t("nav.empty").endswith("contact den Servicedesk.")
    finally:
        current_language.reset(token)


@pytest.mark.parametrize("name", ["gateway.dev.yml", "gateway.compose.yml", "gateway.vm.yml"])
def test_dev_configs_have_english_contact(name):
    """Sonst stünde in englischen Meldungen der deutsche Kontakttext."""
    raw = yaml.safe_load((ROOT / "dev" / name).read_text(encoding="utf-8"))
    assert raw.get("kontakt_en")
    assert raw["kontakt_en"] != raw["kontakt"]


def test_messages_unknown_key_still_raises():
    t = Messages(LOCALES)
    token = current_language.set("en")
    try:
        with pytest.raises(KeyError):
            t("does.not.exist")
    finally:
        current_language.reset(token)


def test_missing_english_text_falls_back_to_german(tmp_path):
    for code in LANGUAGES:
        (tmp_path / f"messages.{code}.yml").write_text("a: Hallo\n" if code == "de" else "b: x\n", encoding="utf-8")
    t = Messages(tmp_path)
    token = current_language.set("en")
    try:
        assert t("a") == "Hallo"
    finally:
        current_language.reset(token)


# ── AK1, AK3: Seiten in der gewählten Sprache ─────────────────────────────────

def test_default_is_german(client):
    html = login(client, "alexandru").get("/").text
    assert '<html lang="de">' in html
    assert "Willkommen" in html
    assert client.get("/").headers["content-language"] == "de"


def test_browser_language_english(client):
    login(client, "alexandru")
    r = client.get("/", headers={"Accept-Language": "en-GB,en;q=0.9"})
    assert '<html lang="en">' in r.text
    assert "Welcome" in r.text and "Willkommen" not in r.text
    assert r.headers["content-language"] == "en"
    assert "Accept-Language" in r.headers["vary"]


def test_browser_language_other_gives_german(client):
    login(client, "alexandru")
    r = client.get("/", headers={"Accept-Language": "fr-FR,fr;q=0.9"})
    assert '<html lang="de">' in r.text


def test_error_page_in_english(client):
    r = client.get("/gibt-es-nicht", headers={"Accept-Language": "en"})
    assert r.status_code in (404, 302)
    login(client, "alexandru")
    r = client.get("/gibt-es-nicht", headers={"Accept-Language": "en"})
    assert r.status_code == 404
    assert "Page not found" in r.text and '<html lang="en">' in r.text
    assert "Error number" in r.text


def test_login_page_in_english(client):
    r = client.get("/login", headers={"Accept-Language": "en"})
    assert "Log in" in r.text and '<html lang="en">' in r.text


def test_nav_in_english_has_own_etag(client):
    login(client, "alexandru")
    de = client.get("/nav")
    en = client.get("/nav", headers={"Accept-Language": "en"})
    assert de.status_code == en.status_code == 200
    assert de.headers["etag"] != en.headers["etag"]
    assert "Hauptnavigation" in de.text and "Main navigation" in en.text
    assert client.get("/nav", headers={"Accept-Language": "en", "If-None-Match": en.headers["etag"]}).status_code == 304
    assert client.get("/nav", headers={"If-None-Match": en.headers["etag"]}).status_code == 200


def test_threadpool_handlers_see_language(client):
    """Die Handler sind synchron und laufen im Thread-Pool: die Sprache muss dort ankommen."""
    login(client, "admin")
    r = client.get("/_portal/status", headers={"Accept-Language": "en"})
    assert r.status_code == 200 and "Operating status" in r.text
    assert "Operating status" not in client.get("/_portal/status").text


# ── AK2, AK7: Umschalter und Cookie ───────────────────────────────────────────

def test_switcher_link_shown_to_other_language(client):
    login(client, "alexandru")
    de = client.get("/").text
    assert 'href="/sprache/en?next=/"' in de and 'lang="en"' in de
    en = client.get("/", headers={"Accept-Language": "en"}).text
    assert 'href="/sprache/de?next=/"' in en


def test_switcher_on_login_page_without_session(client):
    assert 'href="/sprache/en?next=/login' in client.get("/login").text


def test_switcher_keeps_path_and_query(client):
    login(client, "admin")
    html = client.get("/_portal/status").text
    assert 'href="/sprache/en?next=/_portal/status"' in html


def test_switch_sets_cookie_and_returns(client):
    r = client.get("/sprache/en?next=/_portal/status")
    assert r.status_code == 303
    assert r.headers["location"] == "/_portal/status"
    cookie = r.headers["set-cookie"]
    assert "hka_lang=en" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie and "Max-Age=31536000" in cookie
    login(client, "alexandru")
    assert "Welcome" in client.get("/").text


def test_cookie_wins_over_browser_language(client):
    login(client, "alexandru")
    client.cookies.set("hka_lang", "de")
    r = client.get("/", headers={"Accept-Language": "en"})
    assert '<html lang="de">' in r.text


def test_manipulated_cookie_gives_browser_language(client):
    login(client, "alexandru")
    client.cookies.set("hka_lang", "../../etc")
    assert '<html lang="de">' in client.get("/").text
    assert '<html lang="en">' in client.get("/", headers={"Accept-Language": "en"}).text


@pytest.mark.parametrize("code", ["fr", "EN", "de-DE", "xx"])
def test_unknown_language_is_404(client, code):
    r = client.get(f"/sprache/{code}")
    assert r.status_code == 404
    assert "set-cookie" not in r.headers


@pytest.mark.parametrize("target", ["https://evil.example/", "//evil.example", "/\\evil.example", "javascript:alert(1)"])
def test_foreign_next_goes_home(client, target):
    r = client.get("/sprache/en", params={"next": target})
    assert r.status_code == 303
    assert r.headers["location"] == "/"


def test_no_next_goes_home(client):
    assert client.get("/sprache/de").headers["location"] == "/"


@pytest.mark.parametrize("value", ['"false"', '"no"', "1"])
def test_language_switch_must_be_a_boolean(env, value):
    from portal.core.config import ConfigError, load_config
    cfg = env / "gateway.dev.yml"
    cfg.write_text(cfg.read_text(encoding="utf-8") + f"language_switch: {value}\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="language_switch must be true or false"):
        load_config(cfg)
