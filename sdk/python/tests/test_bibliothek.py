"""Bausteine ohne Netz: Pfadregeln, common/, Fakes, Fehlertypen als Konstanten."""

import asyncio
import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from platform_sdk.adapters import transport
from platform_sdk.adapters.bwsync import errors, paths
from platform_sdk.adapters.bwsync.connect import ROUTES, SCRIPT
from platform_sdk.adapters.bwsync.testing import FakeBwSync
from platform_sdk.adapters.noten.testing import FakeNoten
from platform_sdk.common import dates, downloads, sizes
from platform_sdk.context import current_assertion, current_user
from platform_sdk.errors import AdapterError

ROOT = Path(__file__).resolve().parents[1] / "platform_sdk"


@pytest.fixture
def in_request():
    a = current_assertion.set("token")
    u = current_user.set(SimpleNamespace(sub="test-person"))
    yield
    current_assertion.reset(a)
    current_user.reset(u)


def run(coro):
    return asyncio.run(coro)


# --- paths ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["a", "Notizen.pdf", "x" * 255, "Ärger \"x\"", "日本"])
def test_valid_name(name):
    assert paths.valid_name(name)


@pytest.mark.parametrize("name", ["", ".", "..", "x" * 256, " a", "a ", "a/b", "a\\b", "a:b", "50%", "a?", "a#", "a\x00"])
def test_invalid_name(name):
    assert not paths.valid_name(name)


def test_paths():
    assert paths.valid_path("") and not paths.valid_path("", root=False)
    assert paths.valid_path("a/b") and not paths.valid_path("a//b") and not paths.valid_path("a/../b")
    assert not paths.valid_path("a/" * 600)
    assert paths.clean_name("C:\\Users\\x\\Bericht.pdf") == "Bericht.pdf"
    assert paths.clean_name("../a\x07b") == "ab" and paths.clean_name(None) == ""
    assert paths.join("", "a") == "a" and paths.join("a", "b") == "a/b"
    assert paths.parent_of("a/b/c") == "a/b" and paths.parent_of("a") == ""
    assert paths.name_of("a/b/c") == "c"
    assert paths.breadcrumbs("") == []
    assert paths.breadcrumbs("a/b") == [{"name": "a", "path": "a"}, {"name": "b", "path": "a/b"}]


# --- common --------------------------------------------------------------------------------------------------

def test_sizes():
    assert [sizes.format_size(n) for n in (None, 0, 1023, 1024, 1_300_000, 5 * 1024**5)] == [
        "–", "0 B", "1023 B", "1,0 KB", "1,2 MB", "5120,0 TB"]
    assert sizes.format_size(None, empty="") == ""


def test_dates():
    assert dates.format_datetime(None) == "–"
    winter = datetime(2026, 11, 16, 13, 28, tzinfo=UTC)
    if dates.LOCAL_TIME is None:
        pytest.skip("keine Zeitzonendaten")
    assert dates.format_datetime(winter) == "16.11.2026, 14:28"
    assert dates.format_datetime(datetime(2026, 7, 1, 10, 0)) == "01.07.2026, 12:00"  # ohne Zone: UTC


@pytest.mark.parametrize("name,ascii_name", [
    ('Ärger "x".zip', "Arger x.zip"), ("日本.txt", "download.txt"), ("", "download"), ("a\\b\nc", "abc"),
])
def test_content_disposition(name, ascii_name):
    value = downloads.content_disposition(name)
    assert value.startswith(f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'')
    assert "\n" not in value and value.count('"') == 2


def test_download_headers():
    headers = downloads.download_headers("a.zip")
    assert headers["X-Content-Type-Options"] == "nosniff" and headers["Cache-Control"] == "no-store"


# --- Fehlertypen, Bibliothek ohne Oberfläche ----------------------------------------------------------------

def test_fehlertypen_sind_konstanten():
    kinds = {v for k, v in vars(errors).items() if k.isupper() and isinstance(v, str)}
    assert kinds == {"bwsync-not-linked", "bwsync-link-invalid", "bwsync-forbidden", "bwsync-not-found", "bwsync-exists",
                     "bwsync-parent-missing", "bwsync-conflict", "bwsync-too-large", "bwsync-locked",
                     "bwsync-not-a-file", "bwsync-not-a-folder", "bwsync-move-into-self", "bwsync-folder-too-large",
                     "bwsync-link-failed"}
    assert errors.LINK_PROBLEMS == {errors.NOT_LINKED, errors.LINK_INVALID}
    assert transport.BACKEND_UNAVAILABLE == "backend-unavailable"


def test_keine_oberflaeche_unter_adapters_und_common():
    for folder in ("adapters", "common"):
        for file in (ROOT / folder).rglob("*"):
            if "__pycache__" in file.parts or file.is_dir():
                continue
            assert file.suffix in {".py", ".json", ".md", ".js"}, file
            if file.suffix == ".py":
                text = file.read_text(encoding="utf-8")
                assert "<div" not in text and "<p>" not in text and "Bitte " not in text, file


def test_connect():
    assert SCRIPT == "/_sdk/bwsync/connect.js"
    assert set(ROUTES) == {"status", "start", "poll", "disconnect"}


# --- Fakes ---------------------------------------------------------------------------------------------------

def test_fake_bwsync_wie_adapter(in_request):
    fake = FakeBwSync()
    bwsync = fake.client()
    run(bwsync.mkdir("Studium"))
    run(bwsync.upload("Studium/a b.txt", b"hallo"))
    assert [e.name for e in run(bwsync.list("Studium")).entries] == ["a b.txt"]
    assert run(bwsync.download("Studium/a b.txt")) == b"hallo"
    assert fake.calls[1] == ("PUT", "/bwsync/files/Studium/a b.txt", 5)
    for call, status, kind in [
        (lambda: bwsync.mkdir("Studium"), 409, errors.EXISTS),
        (lambda: bwsync.upload("Studium/a b.txt", b""), 412, errors.EXISTS),
        (lambda: bwsync.mkdir("x/y"), 409, errors.PARENT_MISSING),
        (lambda: bwsync.list("fehlt"), 404, errors.NOT_FOUND),
        (lambda: bwsync.move("Studium", "fehlt/x"), 409, errors.PARENT_MISSING),
        (lambda: bwsync.move("Studium", "Studium/x"), 400, errors.MOVE_INTO_SELF),
        (lambda: bwsync.delete("Studium"), 409, errors.NOT_A_FILE),
        (lambda: bwsync.list("Studium/a b.txt"), 409, errors.NOT_A_FOLDER),
        (lambda: bwsync.delete("Studium/a b.txt", folder=True), 409, errors.NOT_A_FOLDER),
        (lambda: bwsync.upload("Studium/gross", b"x" * (10 * 1024 * 1024 + 1)), 413, errors.TOO_LARGE),
    ]:
        with pytest.raises(AdapterError) as err:
            run(call())
        assert (err.value.status, err.value.type) == (status, kind)
    run(bwsync.mkdir("Archiv"))
    run(bwsync.move("Studium", "Archiv/Studium"))
    assert fake.files == {"Archiv/Studium/a b.txt": b"hallo"}
    stream = run(bwsync.download_zip("Archiv"))

    async def read():
        return b"".join([part async for part in stream])
    with zipfile.ZipFile(io.BytesIO(run(read()))) as archive:
        assert archive.namelist() == ["Archiv/Studium/a b.txt"]
    assert stream.closed
    run(bwsync.delete("Archiv", folder=True))
    assert fake.folders == {""} and not fake.files


def test_fake_bwsync_fail_linked_install(in_request):
    fake = FakeBwSync()
    portal = SimpleNamespace(adapters=SimpleNamespace(bwsync="original"))
    fake.install(portal)
    assert run(portal.adapters.bwsync.is_linked()) is True
    fake.linked = False
    assert run(portal.adapters.bwsync.is_linked()) is False
    with pytest.raises(AdapterError) as err:
        run(portal.adapters.bwsync.list())
    assert err.value.type == errors.NOT_LINKED and err.value.status == 403
    fake.fail = (503, None)
    with pytest.raises(AdapterError) as err:
        run(portal.adapters.bwsync.list())
    assert err.value.type == transport.BACKEND_UNAVAILABLE
    fake.uninstall()
    assert portal.adapters.bwsync == "original"


def test_fake_ohne_anfrage():
    with pytest.raises(AdapterError) as err:
        run(FakeBwSync().client().list())
    assert err.value.type == transport.NO_USER_CONTEXT


def test_fake_noten(in_request):
    fake = FakeNoten({"test-person": [
        {"module": "Mathe 1", "semester": "WS 2025/26", "grade": "1,3", "credits": 5},
        {"module": "Info 1", "semester": "SS 2026", "grade": "bestanden", "credits": None},
    ]})
    noten = fake.client()
    assert len(run(noten.list_my_grades()).items) == 2
    assert [g.module for g in run(noten.list_my_grades(semester="SS 2026")).items] == ["Info 1"]
    fake.fail = (504, transport.BACKEND_TIMEOUT)
    with pytest.raises(AdapterError) as err:
        run(noten.list_my_grades())
    assert err.value.type == transport.BACKEND_TIMEOUT


# --- Browser-Skript (connect.js) -----------------------------------------------------------------------------

def test_install_liefert_connect_js_nur_angemeldet():
    from fastapi.testclient import TestClient

    from conftest import make_app, make_portal, make_token
    from platform_sdk.adapters.bwsync import connect as bwsync_connect

    client = TestClient(make_app(make_portal()))
    ok = client.get(SCRIPT, headers={"X-Portal-Assertion": make_token()})
    assert ok.status_code == 200 and ok.headers["content-type"].startswith("text/javascript")
    assert ok.headers["x-content-type-options"] == "nosniff"
    assert ok.content == bwsync_connect.SCRIPT_FILE.read_bytes()
    assert client.get(SCRIPT).status_code == 401


def test_connect_js_ohne_oberflaeche_und_nur_gateway_routen():
    from platform_sdk.adapters.bwsync import connect as bwsync_connect

    js = bwsync_connect.SCRIPT_FILE.read_text(encoding="utf-8")
    for route in ROUTES.values():
        assert f'"{route}"' in js
    for kind in (bwsync_connect.POPUP_BLOCKED, bwsync_connect.EXPIRED, bwsync_connect.ABORTED,
                 bwsync_connect.SESSION_EXPIRED):
        assert f'"{kind}"' in js
    assert "innerHTML" not in js and "textContent" not in js and "createElement" not in js
    assert "tab.opener = null" in js and 'credentials: "same-origin"' in js
    assert "localStorage" not in js and "document." not in js
