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
