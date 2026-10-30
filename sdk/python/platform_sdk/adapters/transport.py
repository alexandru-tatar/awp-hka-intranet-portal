"""Weg zum Adapter-Dienst: HTTP im Betrieb, feste Testdaten im Entwicklungsmodus (06 §7, §8)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

import httpx

from ..context import current_assertion, current_request_id, current_user
from ..errors import AdapterError

FIXTURES = Path(__file__).parent.parent / "fixtures"
NO_USER = "Die Schnittstelle kann nur während einer Anfrage einer angemeldeten Person benutzt werden."
UNAVAILABLE = "Das System ist gerade nicht erreichbar."
TIMEOUT = "Das System antwortet zu langsam."


class Transport(Protocol):
    async def get(self, path: str, params: dict[str, str] | None) -> Any: ...


class HttpTransport:
    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")

    async def get(self, path: str, params: dict[str, str] | None) -> Any:
        token = current_assertion.get()
        if token is None:
            raise AdapterError(500, "no-user-context", NO_USER)
        headers = {"Authorization": f"Bearer {token}"}
        if request_id := current_request_id.get():
            headers["X-Request-Id"] = request_id
        try:
            async with httpx.AsyncClient(timeout=8) as client:  # keine automatische Wiederholung
                response = await client.get(self._base + path, params=params, headers=headers)
        except httpx.TimeoutException:
            raise AdapterError(504, "backend-timeout", TIMEOUT, request_id) from None
        except httpx.HTTPError:
            raise AdapterError(503, "backend-unavailable", UNAVAILABLE, request_id) from None
        if response.is_success:
            return response.json()
        raise _problem(response)


class FixtureTransport:
    """Feste Testdaten aus `fixtures/<system>/<sub>.json`; unbekannte Person: leere Liste."""

    async def get(self, path: str, params: dict[str, str] | None) -> Any:
        user = current_user.get()
        if user is None:
            raise AdapterError(500, "no-user-context", NO_USER)
        if path == "/v1/noten/me/grades":
            file = FIXTURES / "noten" / f"{user.sub}.json"
            data = json.loads(file.read_text(encoding="utf-8")) if file.is_file() else {"items": []}
            if params and params.get("semester"):
                data = {"items": [g for g in data["items"] if g["semester"] == params["semester"]]}
            return data
        raise AdapterError(501, "not-implemented", "Diese Funktion ist hier noch nicht verfügbar.")


def _problem(response: httpx.Response) -> AdapterError:
    try:
        body = response.json()
    except ValueError:
        body = {}
    kind = str(body.get("type", "")).removeprefix("urn:hka:problem:") or "backend-unavailable"
    detail = body.get("detail") or UNAVAILABLE
    return AdapterError(response.status_code, kind, detail, body.get("request_id"))
