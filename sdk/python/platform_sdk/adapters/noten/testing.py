"""Noten für Tests der App: feste Noten je Person im Speicher, ohne Adapter.

Beispiel (pytest)::

    from platform_sdk.adapters.noten.testing import FakeNoten

    fake = FakeNoten({"test-person": [{"module": "Mathe 1", "semester": "WS 2025/26", "grade": "1,3", "credits": 5}]})
    fake.install(portal)
"""

from __future__ import annotations

from typing import Any

from ...context import current_user
from ...errors import AdapterError
from ..transport import NO_USER_CONTEXT
from .client import NotenClient


class FakeNoten:
    """``grades``: sub → Liste von Noten (dicts wie im Modell ``Grade``). ``fail = (status, type)`` wie bei FakeBwSync."""

    def __init__(self, grades: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self.grades = grades or {}
        self.calls: list[tuple[str, str, Any]] = []
        self.fail: tuple[int, str | None] | None = None
        self._installed: tuple[Any, Any] | None = None

    def client(self) -> NotenClient:
        return NotenClient(self)

    def install(self, portal: Any) -> FakeNoten:
        self._installed = (portal, portal.adapters.noten)
        portal.adapters.noten = self.client()
        return self

    def uninstall(self) -> None:
        if self._installed:
            portal, original = self._installed
            portal.adapters.noten = original
            self._installed = None

    async def get(self, path: str, params: dict[str, str] | None) -> Any:
        user = current_user.get()
        if user is None:
            raise AdapterError(500, NO_USER_CONTEXT, "Aufruf außerhalb einer Anfrage einer angemeldeten Person.")
        self.calls.append(("GET", path, params))
        if self.fail:
            status, kind = self.fail
            raise AdapterError(status, kind or "backend-unavailable", "Fake")
        if path != "/v1/noten/me/grades":
            raise AssertionError(f"unerwarteter Aufruf GET {path}")
        items = self.grades.get(user.sub, [])
        if params and params.get("semester"):
            items = [g for g in items if g["semester"] == params["semester"]]
        return {"items": items}
