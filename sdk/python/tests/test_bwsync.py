import asyncio
from types import SimpleNamespace

import httpx
import pytest

from conftest import make_token
from platform_sdk.adapters.clients import BwSyncClient
from platform_sdk.adapters.transport import FixtureTransport, HttpTransport
from platform_sdk.adapters import transport as transport_module
from platform_sdk.context import current_assertion, current_request_id
from platform_sdk.errors import AdapterError


def client_for(monkeypatch, handler):
    def factory(**kwargs):
        return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)
    monkeypatch.setattr(transport_module, "httpx", SimpleNamespace(
        AsyncClient=factory, TimeoutException=httpx.TimeoutException, HTTPError=httpx.HTTPError,
        Timeout=httpx.Timeout,
    ))
    return BwSyncClient(HttpTransport("http://adapter.test"))


def test_binary_roundtrip_and_empty_204(monkeypatch):
    token = make_token()
    files = {}
    methods = []
    def remote(request):
        assert request.headers["authorization"] == f"Bearer {token}"
        assert request.headers["x-request-id"] == "file-test"
        assert request.url.raw_path == b"/bwsync/files/adapter-test/%C3%A4%20test.bin"
        methods.append(request.method)
        if request.method == "PUT":
            assert request.headers["content-type"] == "application/octet-stream"
            files[request.url.path] = request.content
            return httpx.Response(204)
        return httpx.Response(200, content=files[request.url.path])
    client = client_for(monkeypatch, remote)
    async def run():
        current_assertion.set(token)
        current_request_id.set("file-test")
        data = b"\x00\xffbinary\r\n"
        assert await client.upload("adapter-test/ä test.bin", data) is None
        assert await client.download("adapter-test/ä test.bin", max_bytes=len(data)) == data
    asyncio.run(run())
    assert methods == ["PUT", "GET"]


@pytest.mark.parametrize("operation", ["upload", "download"])
def test_missing_assertion_never_contacts_adapter(monkeypatch, operation):
    client = client_for(monkeypatch, lambda request: pytest.fail("unexpected HTTP request"))
    async def run():
        current_assertion.set(None)
        with pytest.raises(AdapterError) as error:
            if operation == "upload":
                await client.upload("file.txt", b"x")
            else:
                await client.download("file.txt")
        assert error.value.type == "no-user-context"
    asyncio.run(run())


@pytest.mark.parametrize("status", [404, 412, 413, 502, 504])
def test_upload_errors_are_not_retried(monkeypatch, status):
    calls = []
    def remote(request):
        calls.append(request)
        return httpx.Response(status, json={"detail": "Adapterfehler"})
    client = client_for(monkeypatch, remote)
    async def run():
        current_assertion.set(make_token())
        with pytest.raises(AdapterError) as error:
            await client.upload("file.txt", b"x")
        assert error.value.status == status
    asyncio.run(run())
    assert len(calls) == 1


@pytest.mark.parametrize("exception,status", [(httpx.ConnectError, 503), (httpx.ReadTimeout, 504)])
def test_network_errors(monkeypatch, exception, status):
    def remote(request):
        raise exception("test failure", request=request)
    client = client_for(monkeypatch, remote)
    async def run():
        current_assertion.set(make_token())
        with pytest.raises(AdapterError) as error:
            await client.download("file.txt")
        assert error.value.status == status
    asyncio.run(run())


def test_download_limit_closes_stream(monkeypatch):
    class Stream(httpx.AsyncByteStream):
        closed = False
        async def __aiter__(self):
            yield b"123"
            yield b"456"
        async def aclose(self):
            self.closed = True
    stream = Stream()
    client = client_for(monkeypatch, lambda request: httpx.Response(200, stream=stream))
    async def run():
        current_assertion.set(make_token())
        with pytest.raises(AdapterError) as error:
            await client.download("file.txt", max_bytes=5)
        assert error.value.status == 413
        assert stream.closed
    asyncio.run(run())


@pytest.mark.parametrize("path", ["", "../file", "/file", "a//b", "https://evil.test/x", "a%2fb"])
def test_paths_cannot_escape_file_route(monkeypatch, path):
    client = client_for(monkeypatch, lambda request: pytest.fail("unexpected HTTP request"))
    with pytest.raises(ValueError):
        asyncio.run(client.upload(path, b"x"))


def test_fixture_mode_does_not_simulate_success():
    client = BwSyncClient(FixtureTransport())
    with pytest.raises(AdapterError) as error:
        asyncio.run(client.upload("file.txt", b"x"))
    assert error.value.status == 501


# --- Ordner: list, mkdir, move, delete (1.0.3-dev) -------------------------------------------------------------

LISTING = {"path": "Studium", "truncated": False, "skipped": 1, "entries": [
    {"name": "Übungen", "type": "folder", "size": 10, "modified": "2026-11-16T13:28:22+00:00"},
    {"name": "a b.pdf", "type": "file", "size": 1200, "modified": None},
]}


def recorder(monkeypatch, status=204, body=None):
    calls = []
    def remote(request):
        calls.append(request)
        if body is not None:
            return httpx.Response(status, json=body)
        return httpx.Response(status)
    return client_for(monkeypatch, remote), calls


def run_as_user(coroutine):
    async def go():
        current_assertion.set(make_token())
        current_request_id.set("explorer-test")
        return await coroutine
    return asyncio.run(go())


def test_list_root_and_subfolder(monkeypatch):
    client, calls = recorder(monkeypatch, 200, LISTING)
    folder = run_as_user(client.list())
    assert calls[0].method == "GET" and calls[0].url.raw_path == b"/bwsync/folders/"
    assert [e.name for e in folder.entries] == ["Übungen", "a b.pdf"] and folder.skipped == 1
    assert folder.entries[0].type == "folder" and folder.entries[0].modified.year == 2026
    run_as_user(client.list("Studium/Semester 5"))
    assert calls[1].url.raw_path == b"/bwsync/folders/Studium/Semester%205"
    assert calls[1].headers["authorization"].startswith("Bearer ")


@pytest.mark.parametrize("bad", [
    {**LISTING, "extra": 1},
    {**LISTING, "entries": [{"name": "../x", "type": "file", "size": 1, "modified": None}]},
    {**LISTING, "entries": [{"name": "a/b", "type": "file", "size": 1, "modified": None}]},
    {**LISTING, "entries": [{"name": "a", "type": "link", "size": 1, "modified": None}]},
    {**LISTING, "entries": [{"name": "a", "type": "file", "size": -1, "modified": None}]},
    {**LISTING, "entries": [{"name": "a", "type": "file", "size": 1, "modified": None}] * 1001},
    [],
])
def test_list_rejects_unexpected_answers(monkeypatch, bad):
    client, _ = recorder(monkeypatch, 200, bad)
    with pytest.raises(AdapterError) as error:
        run_as_user(client.list())
    assert error.value.status == 502 and error.value.type == "contract-violation"


def test_mkdir_move_delete_requests(monkeypatch):
    client, calls = recorder(monkeypatch, 204)
    run_as_user(client.move("Studium/alt.txt", "Archiv/neu ä.txt"))
    run_as_user(client.delete("Archiv/neu ä.txt"))
    run_as_user(client.delete("Leer", folder=True))
    client, mk_calls = recorder(monkeypatch, 201)
    run_as_user(client.mkdir("Neuer Ordner"))
    calls += mk_calls
    assert [(c.method, c.url.raw_path) for c in calls] == [
        ("POST", b"/bwsync/move"), ("DELETE", b"/bwsync/files/Archiv/neu%20%C3%A4.txt"),
        ("DELETE", b"/bwsync/folders/Leer"), ("POST", b"/bwsync/folders/Neuer%20Ordner")]
    import json
    assert json.loads(calls[0].content) == {"from": "Studium/alt.txt", "to": "Archiv/neu ä.txt"}
    assert all(c.headers["x-request-id"] == "explorer-test" for c in calls)


@pytest.mark.parametrize("status,kind", [(409, "bwsync-exists"), (409, "bwsync-parent-missing"),
                                         (403, "bwsync-not-linked"), (403, "bwsync-forbidden")])
def test_adapter_problem_types_reach_the_app(monkeypatch, status, kind):
    client, calls = recorder(monkeypatch, status, {"type": f"urn:hka:problem:{kind}", "detail": "Deutscher Hinweis."})
    with pytest.raises(AdapterError) as error:
        run_as_user(client.mkdir("X"))
    assert (error.value.status, error.value.type, error.value.detail) == (status, kind, "Deutscher Hinweis.")
    assert len(calls) == 1  # keine Wiederholung


def test_send_rejects_unexpected_success_status(monkeypatch):
    client, _ = recorder(monkeypatch, 200, {"ok": True})
    with pytest.raises(AdapterError) as error:
        run_as_user(client.mkdir("X"))
    assert error.value.status == 502 and error.value.type == "contract-violation"


@pytest.mark.parametrize("call", [
    lambda c: c.mkdir(""), lambda c: c.mkdir("../x"), lambda c: c.delete("", folder=True), lambda c: c.delete("a//b"),
    lambda c: c.move("a", "https://evil.test/x"), lambda c: c.move("", "b"), lambda c: c.list("../.."),
    lambda c: c.list("a%2fb"), lambda c: c.mkdir("x" * 256),
])
def test_bad_paths_never_reach_the_adapter(monkeypatch, call):
    client = client_for(monkeypatch, lambda request: pytest.fail("unexpected HTTP request"))
    with pytest.raises(ValueError):
        run_as_user(call(client))


@pytest.mark.parametrize("call", [lambda c: c.list(), lambda c: c.mkdir("X"), lambda c: c.delete("a"),
                                  lambda c: c.move("a", "b")])
def test_fixture_mode_does_not_simulate_folders(call):
    with pytest.raises(AdapterError) as error:
        asyncio.run(call(BwSyncClient(FixtureTransport())))
    assert error.value.status == 501


def test_missing_assertion_never_contacts_adapter_for_folders(monkeypatch):
    client = client_for(monkeypatch, lambda request: pytest.fail("unexpected HTTP request"))
    async def go():
        current_assertion.set(None)
        with pytest.raises(AdapterError) as error:
            await client.mkdir("X")
        assert error.value.type == "no-user-context"
    asyncio.run(go())


def test_download_zip_streams_and_closes(monkeypatch):
    class Stream(httpx.AsyncByteStream):
        closed = False
        async def __aiter__(self):
            yield b"PK\x03\x04"
            yield b"rest"
        async def aclose(self):
            self.closed = True
    stream = Stream()
    seen = []
    def remote(request):
        seen.append(request)
        return httpx.Response(200, stream=stream, headers={"Content-Type": "application/zip"})
    client = client_for(monkeypatch, remote)
    async def run():
        current_assertion.set(make_token())
        result = await client.download_zip("Studium/Semester 5")
        assert not stream.closed  # erst beim Lesen
        assert [chunk async for chunk in result] == [b"PK\x03\x04", b"rest"]
        assert stream.closed
        await result.aclose()  # nochmal schließen schadet nicht
    asyncio.run(run())
    assert seen[0].method == "GET" and seen[0].url.raw_path == b"/bwsync/zip/Studium/Semester%205"


@pytest.mark.parametrize("status,kind", [(404, "bwsync-not-found"), (423, "bwsync-locked"), (403, "bwsync-not-linked")])
def test_download_zip_error_before_answer(monkeypatch, status, kind):
    body = {"type": f"urn:hka:problem:{kind}", "detail": "Text"}
    client = client_for(monkeypatch, lambda request: httpx.Response(status, json=body))
    async def run():
        current_assertion.set(make_token())
        with pytest.raises(AdapterError) as error:
            await client.download_zip("Studium")
        assert error.value.status == status and error.value.type == kind
    asyncio.run(run())


def test_download_zip_rejects_root_and_fixture_mode():
    async def run():
        with pytest.raises(ValueError):
            await BwSyncClient(FixtureTransport()).download_zip("")
        with pytest.raises(AdapterError) as error:
            await BwSyncClient(FixtureTransport()).download_zip("Studium")
        assert error.value.status == 501
    asyncio.run(run())

