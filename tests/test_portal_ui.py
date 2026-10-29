"""Portal-UI: Seiten, Menü, Fehlerseiten, Logout und Zugriff auf Apps; die IDs (UI1 ff.) verweisen auf 04 §12."""

import re

from conftest import login, write_manifest


def nav_labels(html: str) -> list[str]:
    wide = html.split('class="portal-nav__wide"', 1)[1].split("</nav>", 1)[0]
    return re.findall(r"</svg>([^<]+)</a>", wide)


def nav_groups(html: str) -> list[str]:
    wide = html.split('class="portal-nav__wide"', 1)[1].split("</nav>", 1)[0]
    return re.findall(r'<h2 class="nav__group">([^<]+)</h2>', wide)


def test_unauthenticated_home_redirects_to_login(client):
    r = client.get("/")
    assert r.status_code == 302
    assert r.headers["location"] == "/login?next=/"


def test_ui1_student_sees_only_student_apps_in_fixed_order(client):
    html = login(client, "alexandru").get("/").text
    assert nav_groups(html) == ["Studium", "Kommunikation"]          # Verwaltung, Sonstiges empty → omitted
    assert nav_labels(html) == ["Meine Noten", "Stundenplan", "Nachricht senden"]


def test_ui1_items_alphabetical_with_umlauts(client, env):
    write_manifest(env, {"slug": "aerzte", "name": "Ärzte", "category": "Studium",
                         "menu": {"label": "Ärztlicher Dienst", "icon": "info"},
                         "roles": ["student"], "version": "1.0.0"})
    html = login(client, "alexandru").get("/").text
    assert nav_labels(html)[:3] == ["Ärztlicher Dienst", "Meine Noten", "Stundenplan"]


def test_ui2_user_without_roles_sees_empty_text(client):
    html = login(client, "gast").get("/").text
    assert "Für Sie ist im Moment keine Anwendung freigeschaltet" in html
    assert 'class="nav__group"' not in html


def test_ui3_unhealthy_and_registering_apps_absent_from_menu(client):
    html = login(client, "neumann").get("/").text
    labels = nav_labels(html)
    assert "Raum buchen" not in labels          # unhealthy
    assert "Abschlussarbeiten" not in labels    # registering
    assert "Anträge" in labels


def test_ui4_error_pages_have_title_body_request_id_and_home_link(client):
    for status, title in [(403, "Dafür fehlt Ihnen die Berechtigung"), (404, "Seite nicht gefunden"),
                          (503, "Anwendung vorübergehend nicht verfügbar"), (500, "Es ist ein Fehler aufgetreten")]:
        r = client.get(f"/_portal/error/{status}", headers={"X-Request-Id": "abc-123"})
        assert r.status_code == status
        assert f"<h1>{title}</h1>" in r.text
        assert "abc-123" in r.text
        assert 'href="/">' in r.text


def test_ui5_skip_link_first_and_main_focusable(client):
    html = login(client, "alexandru").get("/").text
    body = html.split("<body>", 1)[1]
    assert body.lstrip().startswith('<a class="skip" href="#main">Zum Inhalt springen</a>')
    assert '<main id="main" tabindex="-1"' in html


def test_ui11_nav_fragment_etag_and_kit_header(client):
    login(client, "alexandru")
    r = client.get("/nav", params={"current": "/apps/noten/x"})
    assert r.status_code == 200
    assert r.headers["cache-control"] == "private, max-age=60"
    assert r.headers["x-portal-kit"].startswith("kit-")
    assert 'href="/apps/noten/" aria-current="page"' in r.text
    r2 = client.get("/nav", params={"current": "/apps/noten/x"}, headers={"If-None-Match": r.headers["etag"]})
    assert r2.status_code == 304


def test_ui11_nav_changes_after_registry_change(client, env):
    login(client, "alexandru")
    etag = client.get("/nav").headers["etag"]
    (env / "manifests" / "stundenplan.json").unlink()
    r = client.get("/nav", headers={"If-None-Match": etag})
    assert r.status_code == 200
    assert "Stundenplan" not in r.text


def test_nav_requires_auth(client):
    assert client.get("/nav").status_code == 401


def test_ui14_logout_needs_confirmation_and_csrf(client):
    login(client, "alexandru")
    page = client.get("/logout")
    assert page.status_code == 200
    csrf = re.search(r'name="csrf" value="([^"]+)"', page.text).group(1)
    assert client.post("/logout", data={}).status_code == 400
    assert client.post("/logout", data={"csrf": "foreign"}).status_code == 400
    r = client.post("/logout", data={"csrf": csrf})
    assert r.status_code == 303
    assert client.get("/").status_code == 302


def test_status_page_only_for_platform_admin(client):
    login(client, "alexandru")
    assert client.get("/_portal/status").status_code == 403
    client.cookies.clear()
    login(client, "admin")
    r = client.get("/_portal/status")
    assert r.status_code == 200
    assert "gestört" in r.text and "wird geprüft" in r.text


def test_app_decision_order_matches_verify(client):
    # unknown → 404; role missing → 403 even if unhealthy (no info leak); unhealthy → 503
    login(client, "alexandru")
    assert client.get("/apps/gibtsnicht/").status_code == 404
    assert client.get("/apps/abschlussarbeiten/").status_code == 404      # registering
    assert client.get("/apps/raumbuchung/").status_code == 403            # unhealthy, but no role
    client.cookies.clear()
    login(client, "max")
    assert client.get("/apps/raumbuchung/").status_code == 503
    assert client.get("/apps/antraege/").status_code == 200


def test_app_requires_login_and_keeps_target(client):
    r = client.get("/apps/noten/")
    assert r.status_code == 302
    assert r.headers["location"] == "/login?next=/apps/noten/"


def test_open_redirect_rejected(client):
    for bad in ["//evil.example", "/\\evil", "https://evil", "/_portal/status"]:
        r = client.post("/login", data={"user": "alexandru", "next": bad})
        assert r.headers["location"] == "/"


def test_static_assets_immutable(client):
    css = re.search(r'href="(/_portal/static/kit-[0-9a-f]{12}\.css)"', login(client, "alexandru").get("/").text).group(1)
    r = client.get(css)
    assert r.status_code == 200
    assert r.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_ui7_field_macro_describedby_references_existing_ids(client):
    login(client, "alexandru")
    html = client.post("/apps/nachricht/", data={"subject": ""}).text
    described = re.search(r'id="subject"[^>]*aria-describedby="([^"]+)"', html).group(1).split()
    for ref in described:
        assert f'id="{ref}"' in html
    assert 'aria-invalid="true"' in html
    assert 'role="alert"' in html and 'href="#subject"' in html


def test_dialog_has_exactly_two_buttons(client):
    html = login(client, "alexandru").get("/apps/nachricht/").text
    for actions in re.findall(r'<div class="dialog__actions">(.*?)</div>', html, re.S):
        assert actions.count("<button") == 2
