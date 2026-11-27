"""Dokumentation /_portal/docs: Rolle maintainer, Bearbeiten mit Versionen, Letzte Änderungen, Bilder, Bereinigung."""

import re

import pytest

from conftest import login
from portal.docs import DocStore, sanitize_html
from portal.docs.store import parse_seed, SEED_FILE

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 64
API = "/_portal/docs/api"


def csrf(client) -> str:
    """CSRF-Token aus den Startdaten der Docs-Seite."""
    html = client.get("/_portal/docs").text
    return re.search(r'"csrf": "([^"]+)"', html).group(1)


@pytest.fixture
def editor(client):
    """Client als Testperson mit Rolle maintainer, dazu das CSRF-Token."""
    login(client, "entwickler")
    return client, {"X-CSRF-Token": csrf(client)}


def test_everyone_logged_in_reads_docs_but_only_maintainer_edits(client):
    assert client.get("/_portal/docs").status_code == 302
    r = login(client, "alexandru").get("/_portal/docs")
    assert r.status_code == 200 and '"canEdit": false' in r.text
    footer = client.get("/").text.split('<footer class="site-footer">', 1)[1]
    assert "/_portal/docs" in footer
    assert client.get(f"{API}/pages/faq").status_code == 200
    h = {"X-CSRF-Token": csrf(client)}
    assert client.put(f"{API}/pages/faq", json={"base_version": 1, "html": "<h1>x</h1>"}, headers=h).status_code == 403


@pytest.mark.parametrize(("user", "can_edit"), [("entwickler", "true"), ("admin", "false"), ("max", "false")])
def test_docs_page_with_nonce_csp(client, user, can_edit):
    login(client, user)
    footer = client.get("/").text.split('<footer class="site-footer">', 1)[1].split("</footer>", 1)[0]
    assert re.findall(r'<a class="cta" href="([^"]+)">([^<]+)</a>', footer) == [("/_portal/docs", "Docs")]
    r = client.get("/_portal/docs")
    assert r.status_code == 200 and "<title>AWP Docs" in r.text
    csp = r.headers["content-security-policy"]
    nonce = re.search(r"'nonce-([^']+)'", csp).group(1)
    assert "script-src 'nonce-" in csp and "script-src 'self' 'unsafe-inline'" not in csp
    scripts = re.findall(r"<script(?![^>]*application/json)([^>]*)>", r.text)
    assert scripts and all(f'nonce="{nonce}"' in s for s in scripts)
    assert f'"canEdit": {can_edit}' in r.text


def test_seed_has_all_pages_and_changes_page(editor):
    client, _ = editor
    html = client.get("/_portal/docs").text
    assert html.count('<article class="page" data-page=') == len(parse_seed(SEED_FILE.read_text())) + 1
    assert 'data-page="aenderungen"' in html and "Ausgangsstand der Dokumentation" in html
    assert 'data-updated-by="Projektteam AWP"' in html


def test_edit_creates_version_byline_and_change_entry(editor):
    client, h = editor
    page = client.get(f"{API}/pages/faq").json()
    html = page["html"].replace("<h1>Häufige Fragen</h1>", "<h1>FAQ</h1><p>Neu <script>alert(1)</script></p>")
    r = client.put(f"{API}/pages/faq", json={"base_version": page["version"], "html": html, "note": "FAQ gekürzt"},
                   headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["version"] == 2 and r.json()["title"] == "FAQ" and r.json()["updated_by"] == "Eva Entwicklerin"
    stored = client.get(f"{API}/pages/faq").json()["html"]
    assert "<script" not in stored and "<p>Neu </p>" in stored
    hist = client.get(f"{API}/pages/faq/history").json()["versions"]
    assert [v["version"] for v in hist] == [2, 1] and hist[0]["note"] == "FAQ gekürzt"
    doc = client.get("/_portal/docs").text
    assert 'data-page="faq" data-title="FAQ"' in doc and 'data-updated-by="Eva Entwicklerin"' in doc
    changes = doc.split('data-page="aenderungen"', 1)[1]
    assert changes.index("FAQ gekürzt") < changes.index("Ausgangsstand")
    assert "<b>Eva Entwicklerin</b> hat <a href=\"#faq\">FAQ</a> aktualisiert" in changes


def test_conflict_when_base_version_is_old(editor):
    client, h = editor
    html = client.get(f"{API}/pages/glossar").json()["html"]
    assert client.put(f"{API}/pages/glossar", json={"base_version": 1, "html": html}, headers=h).status_code == 200
    r = client.put(f"{API}/pages/glossar", json={"base_version": 1, "html": html}, headers=h)
    assert r.status_code == 409 and r.json()["current_version"] == 2
    assert "Eva Entwicklerin hat die Seite inzwischen geändert" in r.json()["message"]


def test_restore_publishes_old_version_as_new(editor):
    client, h = editor
    old = client.get(f"{API}/pages/roadmap").json()
    client.put(f"{API}/pages/roadmap", json={"base_version": 1, "html": "<h1>Roadmap</h1><p>leer</p>"}, headers=h)
    r = client.post(f"{API}/pages/roadmap/restore", json={"version": 1}, headers=h)
    assert r.status_code == 200 and r.json()["version"] == 3
    assert client.get(f"{API}/pages/roadmap").json()["html"] == old["html"]
    assert client.get(f"{API}/pages/roadmap/versions/2").json()["html"] == "<h1>Roadmap</h1><p>leer</p>"


def test_create_and_delete_page(editor):
    client, h = editor
    r = client.post(f"{API}/pages", json={"title": "Über Bilder", "group": "Hilfe", "after": "faq"}, headers=h)
    assert r.status_code == 201 and r.json()["slug"] == "ueber-bilder"
    doc = client.get("/_portal/docs").text
    assert doc.index('data-page="faq"') < doc.index('data-page="ueber-bilder"') < doc.index('data-page="support"')
    assert client.delete(f"{API}/pages/ueber-bilder", headers=h).status_code == 204
    doc = client.get("/_portal/docs").text
    assert 'data-page="ueber-bilder"' not in doc and "hat <b>Über Bilder</b> gelöscht" in doc
    assert client.delete(f"{API}/pages/start", headers=h).status_code == 422


def test_writes_need_csrf_and_editor_role(client):
    login(client, "entwickler")
    assert client.put(f"{API}/pages/faq", json={"base_version": 1, "html": "<h1>x</h1>"}).status_code == 400
    client.post("/logout", data={"csrf": csrf(client)})
    login(client, "alexandru")
    assert client.put(f"{API}/pages/faq", json={"base_version": 1, "html": "<h1>x</h1>"}).status_code == 403


def test_image_upload_checks_type_and_is_served(editor):
    client, h = editor
    r = client.post(f"{API}/assets", content=PNG, headers={**h, "Content-Type": "image/png"})
    assert r.status_code == 201
    url = r.json()["url"]
    assert re.fullmatch(r"/_portal/docs/assets/[0-9a-f]{20}\.png", url)
    got = client.get(url)
    assert got.status_code == 200 and got.content == PNG and got.headers["content-type"] == "image/png"
    assert "sandbox" in got.headers["content-security-policy"]
    fake = client.post(f"{API}/assets", content=b"<svg onload=alert(1)>", headers={**h, "Content-Type": "image/png"})
    assert fake.status_code == 415
    svg = client.post(f"{API}/assets", content=b"<svg/>", headers={**h, "Content-Type": "image/svg+xml"})
    assert svg.status_code == 415
    page = client.get(f"{API}/pages/faq").json()
    html = page["html"] + f'<figure class="dx-img img-m"><img src="{url}" alt="Bild"></figure><img src="https://x/y.png">'
    client.put(f"{API}/pages/faq", json={"base_version": 1, "html": html}, headers=h)
    stored = client.get(f"{API}/pages/faq").json()["html"]
    assert f'<img src="{url}" alt="Bild">' in stored and "https://x/y.png" not in stored


def test_upload_limit(editor, env):
    client, h = editor
    limit = client.app.state.portal.doc_write_service.max_upload_bytes
    r = client.post(f"{API}/assets", content=PNG + b"\0" * limit, headers={**h, "Content-Type": "image/png"})
    assert r.status_code == 413 and "MB" in r.json()["message"]


def test_store_without_dir_is_read_only():
    store = DocStore(None)
    assert not store.writable and store.page("start").version == 1
    with pytest.raises(Exception):
        store.create(title="x", group="y", html="", attrs={}, actor="a", note="")


@pytest.mark.parametrize(("dirty", "clean"), [
    ('<p onclick="x()">a</p>', "<p>a</p>"),
    ('<a href="javascript:alert(1)">l</a>', "<a>l</a>"),
    ('<a href=" JaVa\tscript:alert(1)">l</a>', "<a>l</a>"),
    ('<a href="https://h-ka.de" target="_blank">h</a>', '<a href="https://h-ka.de" target="_blank" rel="noopener noreferrer">h</a>'),
    ("<iframe src=x>t</iframe><p>b</p>", "<p>b</p>"),
    ('<svg><use href="javascript:x"/></svg>', "<svg><use/></svg>"),
    ('<svg><foreignObject><img src=x onerror=1></foreignObject></svg>', "<svg></svg>"),
    ('<img src="/_portal/docs/assets/a.png" onerror="x">', '<img src="/_portal/docs/assets/a.png">'),
    ('<img src="data:image/png;base64,AAA">', ""),
    ('<p style="background:url(x)">a</p>', "<p>a</p>"),
    ('<svg class="i" style=""><use href="#i-x"/></svg>', '<svg class="i"><use href="#i-x"/></svg>'),
    ("<form><input type=password name=p></form>", "<input>"),
    ("<p>1 &lt; 2 &amp; 3</p>", "<p>1 &lt; 2 &amp; 3</p>"),
    ("<div><p>offen", "<div><p>offen</p></div>"),
])
def test_sanitize(dirty, clean):
    assert sanitize_html(dirty, asset_prefix="/_portal/docs/assets/") == clean


def test_sanitize_keeps_seed_content():
    """Der Ausgangsstand übersteht die Bereinigung bis auf Schreibweisen (Attributnamen, Entitäten)."""
    for page in parse_seed(SEED_FILE.read_text()):
        out = sanitize_html(page.html, asset_prefix="/_portal/docs/assets/")
        assert len(out) > 0.97 * len(page.html), page.slug
        for tag in ("<svg", "<table", "<details", "<h2", "<button", "<input", "<a ", "<code"):
            assert out.count(tag) == page.html.count(tag), (page.slug, tag)


def _seed(*pages: tuple[str, str]) -> str:
    """Kleine seed.html aus (slug, Text)."""
    return "\n".join(f'<article class="page" data-page="{s}" data-title="{s.upper()}" data-group="G">\n'
                     f"  <h1>{s.upper()}</h1><p>{t}</p>\n</article>" for s, t in pages) + "\n"


@pytest.mark.parametrize("without_seed_json", [False, True])
def test_new_seed_updates_only_pages_nobody_edited(tmp_path, monkeypatch, without_seed_json):
    import portal.docs.store as store_module

    seed = tmp_path / "seed.html"
    monkeypatch.setattr(store_module, "SEED_FILE", seed)
    seed.write_text(_seed(("a", "alt"), ("b", "alt"), ("c", "alt")))
    store = DocStore(tmp_path / "docs")
    store.update("b", base_version=1, title="B", group="G", html="<h1>B</h1><p>von Hand</p>", attrs={},
                 actor="Eva", note="")
    store.delete("c", actor="Eva")
    if without_seed_json:  # Speicher von vor der Übernahme neuer Fassungen (VM)
        (tmp_path / "docs" / "seed.json").unlink()

    seed.write_text(_seed(("a", "neu"), ("b", "neu"), ("c", "neu"), ("d", "neu")))
    store = DocStore(tmp_path / "docs")
    a, b = store.page("a"), store.page("b")
    assert "neu" in a.html and a.version == 2 and a.updated_by == "Projektteam AWP"
    assert "von Hand" in b.html and b.version == 2 and b.updated_by == "Eva"
    assert [p.slug for p in store.pages()] == ["a", "b", "d"]
    assert store.changes(1)[0].slug == "d"
    assert any(c.slug == "a" and c.note == "Ausgangsstand aktualisiert" for c in store.changes())

    store = DocStore(tmp_path / "docs")  # nochmal starten: nichts Neues
    assert store.page("a").version == 2 and len(store.changes()) == len(DocStore(tmp_path / "docs").changes())


def test_admin_adds_and_removes_maintainer_effective_immediately(client):
    login(client, "alexandru")
    client.get("/")  # Besuch: Person erscheint in der Auswahl der Verwaltungsseite
    client.post("/logout", data={"csrf": csrf(client)})
    login(client, "entwickler")
    client.get("/")
    client.post("/logout", data={"csrf": csrf(client)})

    login(client, "admin")
    page = client.get("/_portal/admin").text
    section = page.split('id="maintainers-heading"', 1)[1]
    assert "Eva Entwicklerin" in section and "Rolle aus der Anmeldung" in section
    assert '<option value="dev:alexandru">Alexandru Tatar' in section
    admin_csrf = re.search(r'name="csrf" value="([^"]+)"', page).group(1)
    assert client.post("/_portal/admin/maintainers", data={"csrf": admin_csrf, "sub": ""}).status_code == 422
    r = client.post("/_portal/admin/maintainers", data={"csrf": admin_csrf, "sub": "dev:alexandru"})
    assert r.status_code == 303 and "maintainer_added" in r.headers["location"]
    assert re.search(r"Freigabe von Sam Betrieb am \d\d\.\d\d\.\d{4}", client.get("/_portal/admin").text)
    client.post("/logout", data={"csrf": admin_csrf})

    login(client, "alexandru")  # ohne Rolle maintainer, aber freigegeben
    assert '"canEdit": true' in client.get("/_portal/docs").text
    h = {"X-CSRF-Token": csrf(client)}
    page_json = client.get(f"{API}/pages/faq").json()
    assert client.put(f"{API}/pages/faq", json={"base_version": page_json["version"], "html": page_json["html"]},
                      headers=h).status_code == 200
    client.post("/logout", data={"csrf": h["X-CSRF-Token"]})

    login(client, "admin")
    admin_csrf = csrf(client)
    r = client.post("/_portal/admin/maintainers/delete", data={"csrf": admin_csrf, "sub": "dev:alexandru"})
    assert r.status_code == 303
    assert client.post("/_portal/admin/maintainers/delete", data={"csrf": admin_csrf, "sub": "dev:alexandru"}).status_code == 404
    client.post("/logout", data={"csrf": admin_csrf})
    login(client, "alexandru")
    assert '"canEdit": false' in client.get("/_portal/docs").text


def test_maintainer_routes_need_admin(client):
    login(client, "entwickler")
    assert client.post("/_portal/admin/maintainers", data={"csrf": csrf(client), "sub": "x"}).status_code == 403


@pytest.mark.parametrize(("value", "expected"), [
    ("all", ("*",)), ("[maintainer]", ("maintainer",)),
])
def test_config_read_roles(env, value, expected):
    from portal.core.config import load_config

    path = env / "gateway.dev.yml"
    text = path.read_text(encoding="utf-8").replace("  read_roles: all\n", f"  read_roles: {value}\n")
    path.write_text(text, encoding="utf-8")
    assert load_config(path).docs.read_roles == expected


def test_config_rejects_unknown_docs_role(env):
    from portal.core.config import ConfigError, load_config

    path = env / "gateway.dev.yml"
    path.write_text(path.read_text(encoding="utf-8").replace("edit_roles: [maintainer]", "edit_roles: [chef]"),
                    encoding="utf-8")
    with pytest.raises(ConfigError, match="not in role_vocabulary"):
        load_config(path)
