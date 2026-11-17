"""Weg zum Adapter-Dienst: HTTP im Betrieb, feste Testdaten im Entwicklungsmodus (06 §7, §8)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

import httpx

from ..context import current_assertion, current_request_id, current_user
from ..errors import AdapterError

ADAPTERS = Path(__file__).parent  # Testdaten: adapters/<system>/fixtures/<sub>.json
# Allgemeine Fehlertypen (für alle Systeme). Bedeutung und typische Reaktion: sdk/README.md und die README je System.
BACKEND_UNAVAILABLE = "backend-unavailable"  # Adapter nicht erreichbar oder Antwort ohne eigenen type
BACKEND_TIMEOUT = "backend-timeout"  # Adapter antwortet nicht rechtzeitig
CONTRACT_VIOLATION = "contract-violation"  # Antwort passt nicht zur Beschreibung
NOT_IMPLEMENTED = "not-implemented"  # im Entwicklungsmodus (Testdaten) nicht verfügbar
NO_USER_CONTEXT = "no-user-context"  # Aufruf außerhalb einer Anfrage einer angemeldeten Person (Programmierfehler)
DOWNLOAD_TOO_LARGE = "download-too-large"  # Download größer als max_bytes (Grenze der App)

# detail nur für Logs (Regel 4 in sdk/README.md); ohne Antwort vom Adapter bleibt detail leer.
_NO_USER = "Aufruf außerhalb einer Anfrage einer angemeldeten Person."
_DEV_ONLY = "Im Entwicklungsmodus ohne Adapter nicht verfügbar (Gateway-Testbetrieb nötig)."


class Transport(Protocol):
    async def get(self, path: str, params: dict[str, str] | None) -> Any: ...
    async def send(self, method: str, path: str, body: Any | None = None) -> None: ...
    async def put_bytes(self, path: str, data: bytes) -> None: ...
    async def get_bytes(self, path: str, *, max_bytes: int) -> bytes: ...
    async def open_stream(self, path: str) -> AdapterStream: ...


class AdapterStream:
    """Antwortinhalt des Adapters zum Durchreichen (z. B. ``StreamingResponse(stream, …)``), ohne ihn ganz zu laden.

    Fehler des Adapters kommen schon beim Öffnen als :class:`AdapterError`, also bevor die App antwortet.
    Der Strom schließt sich am Ende selbst; bricht die App vorher ab, ``await stream.aclose()`` aufrufen
    (z. B. ``background=BackgroundTask(stream.aclose)``). Mehrfaches Schließen schadet nicht.
    """

    def __init__(self, client: httpx.AsyncClient, response: httpx.Response) -> None:
        self._client = client
        self._response = response
        self._closed = False

    async def __aiter__(self):
        try:
            async for chunk in self._response.aiter_bytes():
                yield chunk
        finally:
            await self.aclose()

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._response.aclose()
        await self._client.aclose()


class HttpTransport:
    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")

    async def put_bytes(self, path: str, data: bytes) -> None:
        await self._file_request("PUT", path, data=data)

    async def get_bytes(self, path: str, *, max_bytes: int) -> bytes:
        if max_bytes < 0:
            raise ValueError("max_bytes muss nichtnegativ sein.")
        return await self._file_request("GET", path, max_bytes=max_bytes)

    async def _file_request(self, method: str, path: str, *, data: bytes | None = None,
                            max_bytes: int = 0) -> bytes:
        token = current_assertion.get()
        if token is None:
            raise AdapterError(500, NO_USER_CONTEXT, _NO_USER)
        request_id = current_request_id.get()
        headers = {"Authorization": f"Bearer {token}"}
        if request_id:
            headers["X-Request-Id"] = request_id
        if method == "PUT":
            headers["Content-Type"] = "application/octet-stream"
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
                async with client.stream(method, self._base + path, headers=headers, content=data) as response:
                    if not response.is_success:
                        await response.aread()
                        raise _problem(response)
                    if response.status_code != (204 if method == "PUT" else 200):
                        raise AdapterError(502, CONTRACT_VIOLATION, "", request_id)
                    if method == "PUT":
                        return b""  # 204 has no JSON body.
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(body) + len(chunk) > max_bytes:
                            raise AdapterError(413, DOWNLOAD_TOO_LARGE, f"mehr als max_bytes={max_bytes}", request_id)
                        body.extend(chunk)
                    return bytes(body)
        except httpx.TimeoutException:
            raise AdapterError(504, BACKEND_TIMEOUT, "", request_id) from None
        except httpx.HTTPError:
            raise AdapterError(503, BACKEND_UNAVAILABLE, "", request_id) from None

    async def open_stream(self, path: str) -> AdapterStream:
        """GET mit gestreamter Antwort (200), z. B. ZIP eines Ordners. Ohne Obergrenze; Verbindung 5 s, sonst 60 s."""
        token = current_assertion.get()
        if token is None:
            raise AdapterError(500, NO_USER_CONTEXT, _NO_USER)
        request_id = current_request_id.get()
        headers = {"Authorization": f"Bearer {token}"}
        if request_id:
            headers["X-Request-Id"] = request_id
        client = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0), follow_redirects=False)
        try:
            response = await client.send(client.build_request("GET", self._base + path, headers=headers), stream=True)
        except httpx.TimeoutException:
            await client.aclose()
            raise AdapterError(504, BACKEND_TIMEOUT, "", request_id) from None
        except httpx.HTTPError:
            await client.aclose()
            raise AdapterError(503, BACKEND_UNAVAILABLE, "", request_id) from None
        if response.status_code != 200:
            await response.aread()
            await response.aclose()
            await client.aclose()
            if not response.is_success:
                raise _problem(response)
            raise AdapterError(502, CONTRACT_VIOLATION, "", request_id)
        return AdapterStream(client, response)

    async def get(self, path: str, params: dict[str, str] | None) -> Any:
        token = current_assertion.get()
        if token is None:
            raise AdapterError(500, NO_USER_CONTEXT, _NO_USER)
        headers = {"Authorization": f"Bearer {token}"}
        if request_id := current_request_id.get():
            headers["X-Request-Id"] = request_id
        try:
            async with httpx.AsyncClient(timeout=8) as client:  # keine automatische Wiederholung
                response = await client.get(self._base + path, params=params, headers=headers)
        except httpx.TimeoutException:
            raise AdapterError(504, BACKEND_TIMEOUT, "", request_id) from None
        except httpx.HTTPError:
            raise AdapterError(503, BACKEND_UNAVAILABLE, "", request_id) from None
        if response.is_success:
            return response.json()
        raise _problem(response)


    async def send(self, method: str, path: str, body: Any | None = None) -> None:
        """POST/DELETE ohne Antwortinhalt (201 oder 204), z. B. Ordner anlegen, verschieben, löschen."""
        token = current_assertion.get()
        if token is None:
            raise AdapterError(500, NO_USER_CONTEXT, _NO_USER)
        headers = {"Authorization": f"Bearer {token}"}
        request_id = current_request_id.get()
        if request_id:
            headers["X-Request-Id"] = request_id
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:  # keine Wiederholung
                response = await client.request(method, self._base + path, headers=headers, json=body)
        except httpx.TimeoutException:
            raise AdapterError(504, BACKEND_TIMEOUT, "", request_id) from None
        except httpx.HTTPError:
            raise AdapterError(503, BACKEND_UNAVAILABLE, "", request_id) from None
        if not response.is_success:
            raise _problem(response)
        if response.status_code not in (201, 204):
            raise AdapterError(502, CONTRACT_VIOLATION, "", request_id)


class FixtureTransport:
    """Feste Testdaten aus `adapters/<system>/fixtures/<sub>.json`; unbekannte Person: leere Liste."""

    async def put_bytes(self, path: str, data: bytes) -> None:
        raise AdapterError(501, NOT_IMPLEMENTED, _DEV_ONLY)

    async def get_bytes(self, path: str, *, max_bytes: int) -> bytes:
        raise AdapterError(501, NOT_IMPLEMENTED, _DEV_ONLY)

    async def open_stream(self, path: str) -> AdapterStream:
        raise AdapterError(501, NOT_IMPLEMENTED, _DEV_ONLY)

    async def send(self, method: str, path: str, body: Any | None = None) -> None:
        raise AdapterError(501, NOT_IMPLEMENTED, _DEV_ONLY)

    async def get(self, path: str, params: dict[str, str] | None) -> Any:
        if path.startswith("/bwsync/"):
            raise AdapterError(501, NOT_IMPLEMENTED, _DEV_ONLY)
        user = current_user.get()
        if user is None:
            raise AdapterError(500, NO_USER_CONTEXT, _NO_USER)
        if path == "/v1/noten/me/grades":
            file = ADAPTERS / "noten" / "fixtures" / f"{user.sub}.json"
            data = json.loads(file.read_text(encoding="utf-8")) if file.is_file() else {"items": []}
            if params and params.get("semester"):
                data = {"items": [g for g in data["items"] if g["semester"] == params["semester"]]}
            return data
        raise AdapterError(501, NOT_IMPLEMENTED, _DEV_ONLY)


def _problem(response: httpx.Response) -> AdapterError:
    try:
        body = response.json()
    except ValueError:
        body = {}
    kind = str(body.get("type", "")).removeprefix("urn:hka:problem:") or BACKEND_UNAVAILABLE
    detail = str(body.get("detail") or "")
    return AdapterError(response.status_code, kind, detail, body.get("request_id"))
