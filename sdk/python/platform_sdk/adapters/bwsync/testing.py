"""bwSync&Share für Tests der App: ein Konto im Speicher, das sich wie der Adapter verhält (gleiche Fehlertypen).

Beispiel (pytest)::

    from platform_sdk.adapters.bwsync.testing import FakeBwSync

    @pytest.fixture
    def bwsync():
        fake = FakeBwSync()
        fake.install(portal)          # portal.adapters.bwsync arbeitet jetzt mit dem Fake
        yield fake
        fake.uninstall()
"""

from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime
from typing import Any
from urllib.parse import unquote

from ...context import current_assertion
from ...errors import AdapterError
from ..transport import BACKEND_UNAVAILABLE, DOWNLOAD_TOO_LARGE, NO_USER_CONTEXT
from . import errors
from .client import BwSyncClient

MODIFIED = datetime(2026, 11, 16, 13, 28, 22, tzinfo=UTC).isoformat()
FILES, FOLDERS, ZIP = "/bwsync/files/", "/bwsync/folders/", "/bwsync/zip/"


class FakeStream:
    """Wie ``AdapterStream``: Inhalt in Stücken, ``aclose`` darf mehrfach kommen."""

    def __init__(self, data: bytes, chunk: int = 64 * 1024) -> None:
        self._parts = [data[i:i + chunk] for i in range(0, len(data), chunk)] or [b""]
        self.closed = False

    async def __aiter__(self):
        try:
            for part in self._parts:
                yield part
        finally:
            await self.aclose()

    async def aclose(self) -> None:
        self.closed = True


class FakeBwSync:
    """Konto im Speicher. ``folders`` (Pfade, ``""`` = Wurzel) und ``files`` (Pfad → Inhalt) darf der Test setzen.

    - ``calls``: jeder Aufruf als ``(methode, pfad, body)`` (Pfad ohne URL-Kodierung).
    - ``fail = (status, type)``: jeder folgende Aufruf scheitert so (``type`` None → ``backend-unavailable``).
    - ``linked``: Antwort von ``is_linked()``; ``False`` lässt alle Dateiaufrufe mit ``bwsync-not-linked`` scheitern.
    - ``listing``: feste Antwort (dict) für ``list()``, z. B. um ``truncated``/``skipped`` zu testen.
    """

    def __init__(self) -> None:
        self.folders: set[str] = {""}
        self.files: dict[str, bytes] = {}
        self.calls: list[tuple[str, str, Any]] = []
        self.fail: tuple[int, str | None] | None = None
        self.linked = True
        self.listing: dict | None = None
        self.streams: list[FakeStream] = []
        self._installed: tuple[Any, Any] | None = None

    # --- Einbau -----------------------------------------------------------------------------------------------

    def client(self) -> BwSyncClient:
        return BwSyncClient(self)

    def install(self, portal: Any) -> FakeBwSync:
        """``portal.adapters.bwsync`` durch einen Client mit diesem Fake ersetzen (``uninstall`` stellt zurück)."""
        self._installed = (portal, portal.adapters.bwsync)
        portal.adapters.bwsync = self.client()
        return self

    def uninstall(self) -> None:
        if self._installed:
            portal, original = self._installed
            portal.adapters.bwsync = original
            self._installed = None

    # --- Hilfen -----------------------------------------------------------------------------------------------

    def add_file(self, path: str, data: bytes = b"") -> None:
        """Datei samt fehlender Elternordner anlegen."""
        parts = path.split("/")
        for i in range(1, len(parts)):
            self.folders.add("/".join(parts[:i]))
        self.files[path] = data

    def exists(self, path: str) -> bool:
        return path in self.folders or path in self.files

    @staticmethod
    def _parent(path: str) -> str:
        return path.rsplit("/", 1)[0] if "/" in path else ""

    def _children(self, path: str) -> list[str]:
        return [p for p in self.folders | set(self.files) if p and self._parent(p) == path]

    def _call(self, method: str, path: str, body: Any = None) -> str:
        if current_assertion.get() is None:  # wie der echte Transport: nur während einer Anfrage
            raise AdapterError(500, NO_USER_CONTEXT, "Aufruf außerhalb einer Anfrage einer angemeldeten Person.")
        path = unquote(path)
        self.calls.append((method, path, body))
        if self.fail:
            status, kind = self.fail
            raise AdapterError(status, kind or BACKEND_UNAVAILABLE, "Fake")
        if not self.linked and path != "/bwsync/link":
            raise AdapterError(403, errors.NOT_LINKED, "Fake")
        return path

    @staticmethod
    def _error(status: int, kind: str) -> AdapterError:
        return AdapterError(status, kind, "Fake")

    # --- Transport (wie HttpTransport) -------------------------------------------------------------------------

    async def get(self, path: str, params: dict[str, str] | None) -> Any:
        path = self._call("GET", path)
        if path == "/bwsync/link":
            return {"linked": self.linked}
        if not path.startswith(FOLDERS):
            raise AssertionError(f"unerwarteter Aufruf GET {path}")
        rel = path.removeprefix(FOLDERS)
        if self.listing is not None:
            return self.listing
        if rel in self.files:
            raise self._error(409, errors.NOT_A_FOLDER)
        if rel not in self.folders:
            raise self._error(404, errors.NOT_FOUND)
        names = sorted(self._children(rel), key=lambda p: (p not in self.folders, p.lower()))
        entries = [
            {
                "name": p.rsplit("/", 1)[-1],
                "type": "folder" if p in self.folders else "file",
                "size": None if p in self.folders else len(self.files[p]),
                "modified": MODIFIED,
            }
            for p in names
        ]
        return {"path": rel, "entries": entries, "truncated": False, "skipped": 0}

    async def send(self, method: str, path: str, body: Any | None = None) -> None:
        path = self._call(method, path, body)
        if path == "/bwsync/move" and method == "POST":
            return self._move(body["from"], body["to"])
        if path.startswith(FOLDERS):
            rel = path.removeprefix(FOLDERS)
            if method == "POST":
                if self.exists(rel):
                    raise self._error(409, errors.EXISTS)
                if self._parent(rel) not in self.folders:
                    raise self._error(409, errors.PARENT_MISSING)
                self.folders.add(rel)
                return None
            if method == "DELETE":
                if rel in self.files:
                    raise self._error(409, errors.NOT_A_FOLDER)
                if rel == "" or rel not in self.folders:
                    raise self._error(404, errors.NOT_FOUND)
                # wie der Adapter: mit allem Inhalt (bwSync&Share legt es in den Papierkorb)
                self.folders = {f for f in self.folders if f != rel and not f.startswith(rel + "/")}
                self.files = {k: v for k, v in self.files.items() if not k.startswith(rel + "/")}
                return None
        if path.startswith(FILES) and method == "DELETE":
            rel = path.removeprefix(FILES)
            if rel in self.folders:
                raise self._error(409, errors.NOT_A_FILE)
            if rel not in self.files:
                raise self._error(404, errors.NOT_FOUND)
            del self.files[rel]
            return None
        raise AssertionError(f"unerwarteter Aufruf {method} {path}")

    def _move(self, source: str, target: str) -> None:
        if source == target or target.startswith(source + "/"):
            raise self._error(400, errors.MOVE_INTO_SELF)
        if not self.exists(source):
            raise self._error(404, errors.NOT_FOUND)
        if self.exists(target):
            raise self._error(409, errors.EXISTS)
        if self._parent(target) not in self.folders:
            raise self._error(409, errors.PARENT_MISSING)
        if source in self.files:
            self.files[target] = self.files.pop(source)
            return
        for p in sorted(self.folders):
            if p == source or p.startswith(source + "/"):
                self.folders.discard(p)
                self.folders.add(target + p[len(source):])
        for p in list(self.files):
            if p.startswith(source + "/"):
                self.files[target + p[len(source):]] = self.files.pop(p)

    async def put_bytes(self, path: str, data: bytes) -> None:
        rel = self._call("PUT", path, len(data)).removeprefix(FILES)
        if len(data) > 10 * 1024 * 1024:
            raise self._error(413, errors.TOO_LARGE)
        if self.exists(rel):
            raise self._error(412, errors.EXISTS)
        if self._parent(rel) not in self.folders:
            raise self._error(409, errors.PARENT_MISSING)
        self.files[rel] = data

    async def get_bytes(self, path: str, *, max_bytes: int) -> bytes:
        rel = self._call("GET", path).removeprefix(FILES)
        if rel not in self.files:
            raise self._error(404, errors.NOT_FOUND)
        if len(self.files[rel]) > max_bytes:
            raise AdapterError(413, DOWNLOAD_TOO_LARGE, f"mehr als max_bytes={max_bytes}")
        return self.files[rel]

    async def open_stream(self, path: str) -> FakeStream:
        rel = self._call("GET", path).removeprefix(ZIP)
        if rel == "" or rel not in self.folders:
            raise self._error(404, errors.NOT_FOUND)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, data in sorted(self.files.items()):
                if name.startswith(rel + "/"):
                    archive.writestr(name, data)
        stream = FakeStream(buffer.getvalue())
        self.streams.append(stream)
        return stream
