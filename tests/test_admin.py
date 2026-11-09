"""Verwaltungsseite /_portal/admin: Apps ansehen, entfernen, Rollen der Apps und Grants ändern (nur platform-admin)."""

import re
from datetime import datetime, timezone

import pytest
import yaml
from fastapi.testclient import TestClient

from conftest import login
from portal.app import create_app
from portal.auth.grants import GrantStore
from portal.auth.roles import RoleMapper, load_role_mapper

BASE = "/_portal/admin"


def csrf_of(client: TestClient) -> str:
    """CSRF-Token der Session aus der Verwaltungsseite lesen."""
    return re.search(r'name="csrf" value="([^"]+)"', client.get(BASE).text).group(1)


def make_client(env, *, write: bool = True, grants: bool = True, owners: bool = True) -> TestClient:
    """Test-Client mit Verwaltungsseite; die Konfiguration der Kopie von ``dev/`` wird angepasst."""
    cfg = env / "gateway.dev.yml"
    text = cfg.read_text(encoding="utf-8").split("\nregistry:")[0].rstrip("\n") + "\n"
    if grants:
        (env / "grants.yml").write_text("grants:\n  - sub: abc-1\n    roles: [pilot-tester]\n", encoding="utf-8")
        text += "grants_file: grants.yml\n"
    if owners:
        text += f"registry:\n  owners_file: owners.json\n  admin_write: {'true' if write else 'false'}\n"
    cfg.write_text(text, encoding="utf-8")
    return TestClient(create_app(cfg), follow_redirects=False)


@pytest.fixture
def admin(env) -> TestClient:
    return login(make_client(env), "admin")


def test_page_only_for_platform_admin(env):
    client = make_client(env)
    assert client.get(BASE).status_code == 302          # nicht angemeldet: Login
    login(client, "alexandru")
    assert client.get(BASE).status_code == 403
    assert client.post(f"{BASE}/apps/noten/remove", data={"csrf": "x"}).status_code == 403
    assert client.post(f"{BASE}/grants", data={"csrf": "x", "sub": "a"}).status_code == 403


def test_header_link_only_for_platform_admin(env):
    client = make_client(env)
    assert BASE not in login(client, "alexandru").get("/").text
    client.cookies.clear()
    assert BASE in login(client, "admin").get("/").text


def test_page_lists_all_apps_with_status_roles_and_grants(admin):
    r = admin.get(BASE)
    assert r.status_code == 200
    for slug in ("noten", "stundenplan", "nachricht", "antraege", "raumbuchung", "abschlussarbeiten"):
        assert f"/_portal/admin/apps/{slug}/remove" in r.text
    assert "gestört" in r.text and "wird geprüft" in r.text and "in Betrieb" in r.text
    assert "von Hand eingerichtet" in r.text            # noch keine Besitzerdatei
    assert "abc-1" in r.text and "pilot-tester" in r.text


def test_remove_app_needs_csrf_and_removes_from_menu(env, admin):
    before = len(list((env / "manifests").glob("*.json")))
    assert admin.post(f"{BASE}/apps/noten/remove", data={"csrf": "falsch"}).status_code == 400
    assert len(list((env / "manifests").glob("*.json"))) == before
    r = admin.post(f"{BASE}/apps/noten/remove", data={"csrf": csrf_of(admin)})
    assert r.status_code == 303 and r.headers["location"] == f"{BASE}?notice=app_removed"
    assert not (env / "manifests" / "noten.json").exists()
    assert "stillgelegt" in admin.get(BASE).text
    assert "Die Anwendung wurde entfernt" in admin.get(r.headers["location"]).text
    assert "/apps/noten/" not in admin.get("/").text
    # Doppelt entfernen und Unbekanntes: 404, nichts ändert sich
    assert admin.post(f"{BASE}/apps/noten/remove", data={"csrf": csrf_of(admin)}).status_code == 404
    assert admin.post(f"{BASE}/apps/gibtsnicht/remove", data={"csrf": csrf_of(admin)}).status_code == 404


def test_set_app_roles_rewrites_manifest_and_menu(env, admin):
    r = admin.post(f"{BASE}/apps/noten/roles", data={"csrf": csrf_of(admin), "roles": ["student", "pilot-tester"]})
    assert r.status_code == 303 and r.headers["location"] == f"{BASE}?notice=app_roles"
    import json
    manifest = json.loads((env / "manifests" / "noten.json").read_text(encoding="utf-8"))
    assert manifest["roles"] == ["pilot-tester", "student"] and manifest["slug"] == "noten"
    assert manifest["menu"] == {"label": "Meine Noten", "icon": "grades"}      # alles andere bleibt
    client = login(TestClient(admin.app, follow_redirects=False), "neumann")    # Rolle professor
    assert "/apps/noten/" not in client.get("/").text


def test_set_app_roles_rejects_empty_and_unknown(admin, env):
    before = (env / "manifests" / "noten.json").read_bytes()
    r = admin.post(f"{BASE}/apps/noten/roles", data={"csrf": csrf_of(admin)})
    assert r.status_code == 422 and "mindestens eine Rolle" in r.text
    r = admin.post(f"{BASE}/apps/noten/roles", data={"csrf": csrf_of(admin), "roles": ["gott"]})
    assert r.status_code == 422 and "gibt es nicht" in r.text
    assert admin.post(f"{BASE}/apps/gibtsnicht/roles", data={"csrf": csrf_of(admin), "roles": ["student"]}).status_code == 404
    assert admin.post(f"{BASE}/apps/noten/roles", data={"csrf": "falsch", "roles": ["student"]}).status_code == 400
    assert (env / "manifests" / "noten.json").read_bytes() == before


def test_grants_set_change_and_delete(env, admin):
    token = csrf_of(admin)
    r = admin.post(f"{BASE}/grants", data={"csrf": token, "sub": "neu-2", "roles": ["employee", "pilot-tester"]})
    assert r.status_code == 303
    data = yaml.safe_load((env / "grants.yml").read_text(encoding="utf-8"))
    assert data["grants"] == [{"sub": "abc-1", "roles": ["pilot-tester"]},
                              {"sub": "neu-2", "roles": ["employee", "pilot-tester"]}]
    admin.post(f"{BASE}/grants", data={"csrf": token, "sub": "abc-1", "roles": ["employee"]})
    assert yaml.safe_load((env / "grants.yml").read_text(encoding="utf-8"))["grants"][0] == {"sub": "abc-1", "roles": ["employee"]}
    assert admin.post(f"{BASE}/grants/delete", data={"csrf": "falsch", "sub": "abc-1"}).status_code == 400
    assert admin.post(f"{BASE}/grants/delete", data={"csrf": token, "sub": "abc-1"}).status_code == 303
    assert admin.post(f"{BASE}/grants/delete", data={"csrf": token, "sub": "abc-1"}).status_code == 404
    # ohne Rollen entfällt der Eintrag
    admin.post(f"{BASE}/grants", data={"csrf": token, "sub": "neu-2"})
    assert yaml.safe_load((env / "grants.yml").read_text(encoding="utf-8"))["grants"] == []


def test_grants_reject_empty_sub_and_unknown_role(admin, env):
    before = (env / "grants.yml").read_bytes()
    assert admin.post(f"{BASE}/grants", data={"csrf": csrf_of(admin), "sub": "  ", "roles": ["student"]}).status_code == 422
    r = admin.post(f"{BASE}/grants", data={"csrf": csrf_of(admin), "sub": "x", "roles": ["gott"]})
    assert r.status_code == 422
    assert (env / "grants.yml").read_bytes() == before


def test_grants_reach_the_role_mapper_without_restart(env):
    store = GrantStore(env / "roles-grants.yml")                          # Datei fehlt: keine Grants
    assert dict(store) == {}
    store.set("abc", frozenset({"employee"}))
    mapper = load_role_mapper(env / "roles.yml", None, grants=store)
    assert mapper.map_roles("abc", {}) == {"employee"}
    store.set("abc", frozenset({"professor"}))
    assert mapper.map_roles("abc", {}) == {"professor"}
    (env / "roles-grants.yml").write_text("grants:\n  - sub: abc\n    roles: [student]\n", encoding="utf-8")  # von Hand
    import os
    os.utime(env / "roles-grants.yml", ns=(10**18, 10**18 + 5))
    assert mapper.map_roles("abc", {}) == {"student"}
    assert isinstance(mapper, RoleMapper)


def test_read_only_page_shows_notice_and_refuses_changes(env):
    client = login(make_client(env, write=False), "admin")
    r = client.get(BASE)
    assert r.status_code == 200 and "nur lesend" in r.text and "/remove" not in r.text
    token = csrf_of(client)
    assert client.post(f"{BASE}/apps/noten/remove", data={"csrf": token}).status_code == 403
    assert client.post(f"{BASE}/apps/noten/roles", data={"csrf": token, "roles": ["student"]}).status_code == 403
    assert client.post(f"{BASE}/grants", data={"csrf": token, "sub": "x", "roles": ["student"]}).status_code == 403
    assert (env / "manifests" / "noten.json").exists()


def test_without_registry_section_page_still_renders_read_only(env):
    client = login(make_client(env, owners=False, grants=False), "admin")
    r = client.get(BASE)
    assert r.status_code == 200 and "nur lesend" in r.text and "Zusätzliche Rollen je Person" not in r.text


def test_admin_config_needs_owners_file(env):
    cfg = env / "gateway.dev.yml"
    cfg.write_text(cfg.read_text(encoding="utf-8").split("\nregistry:")[0] + "\nregistry:\n  admin_write: true\n",
                   encoding="utf-8")
    from portal.core.config import ConfigError, load_config
    with pytest.raises(ConfigError, match="admin_write needs owners_file"):
        load_config(cfg)


def test_removed_name_stays_bound_and_retired_is_listed(env, admin):
    admin.post(f"{BASE}/apps/noten/remove", data={"csrf": csrf_of(admin)})
    import json
    retired = json.loads((env / "retired.json").read_text(encoding="utf-8"))
    assert "noten" in retired and datetime.fromisoformat(retired["noten"]).tzinfo is timezone.utc


def test_missing_grants_file_is_allowed_with_admin_write_and_created_on_first_change(env):
    client = make_client(env, grants=False)
    cfg = env / "gateway.dev.yml"
    cfg.write_text("grants_file: neu/grants.yml\n" + cfg.read_text(encoding="utf-8"), encoding="utf-8")
    (env / "neu").mkdir()
    client = login(TestClient(create_app(cfg), follow_redirects=False), "admin")
    assert client.get(BASE).status_code == 200
    token = csrf_of(client)
    assert client.post(f"{BASE}/grants", data={"csrf": token, "sub": "x", "roles": ["student"]}).status_code == 303
    assert yaml.safe_load((env / "neu" / "grants.yml").read_text(encoding="utf-8"))["grants"] == [
        {"sub": "x", "roles": ["student"]}]

