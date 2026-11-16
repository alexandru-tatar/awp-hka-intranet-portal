"""Clients je System (06 §8)."""

from __future__ import annotations

from urllib.parse import quote

from pydantic import ValidationError

from ..errors import AdapterError
from .models import Folder, GradeList
from .transport import Transport

CONTRACT_VIOLATION = "Das System hat unerwartete Daten geliefert. Bitte versuchen Sie es später noch einmal."


class BwSyncClient:
    """Dateien und Ordner im bwSync&Share-Konto der angemeldeten Person (über den bwSync-Adapter).

    Pfade sind relativ zur Wurzel des Kontos, z. B. ``"Studium/Notizen.pdf"``; ``""`` ist die Wurzel
    (nur bei :meth:`list`). Fehler kommen als :class:`AdapterError`; ``type`` nennt den Fall, z. B.
    ``bwsync-not-linked``, ``bwsync-exists``, ``bwsync-parent-missing``, ``bwsync-folder-not-empty``.
    """

    def __init__(self, transport: Transport) -> None:
        self._t = transport

    @staticmethod
    def _rel(path: str) -> str:
        if (not path or len(path) > 1024 or any(c in path for c in "\\%?#:")
                or any(ord(c) < 32 or ord(c) == 127 for c in path)
                or any(part in ("", ".", "..") or len(part) > 255 for part in path.split("/"))):
            raise ValueError("Ein relativer Dateipfad ohne Traversal ist erforderlich.")
        return path

    @classmethod
    def _path(cls, path: str) -> str:
        return "/bwsync/files/" + quote(cls._rel(path), safe="/")

    @classmethod
    def _folder(cls, path: str, *, root: bool = False) -> str:
        if root and path == "":
            return "/bwsync/folders/"
        return "/bwsync/folders/" + quote(cls._rel(path), safe="/")

    async def upload(self, path: str, data: bytes) -> None:
        """Neue Datei anlegen (überschreibt nie: vorhanden → AdapterError 412)."""
        await self._t.put_bytes(self._path(path), data)

    async def download(self, path: str, *, max_bytes: int = 10_000_000) -> bytes:
        return await self._t.get_bytes(self._path(path), max_bytes=max_bytes)

    async def list(self, path: str = "") -> Folder:
        """Direkte Einträge eines Ordners (Scope ``bwsync:read``)."""
        data = await self._t.get(self._folder(path, root=True), None)
        try:
            return Folder.model_validate(data)
        except ValidationError:
            raise AdapterError(502, "contract-violation", CONTRACT_VIOLATION) from None

    async def mkdir(self, path: str) -> None:
        """Ordner anlegen (Scope ``bwsync:write``); vorhanden → ``bwsync-exists``."""
        await self._t.send("POST", self._folder(path))

    async def move(self, source: str, target: str) -> None:
        """Verschieben oder umbenennen, nie überschreiben (Scope ``bwsync:write``); Ziel vorhanden → ``bwsync-exists``."""
        await self._t.send("POST", "/bwsync/move", {"from": self._rel(source), "to": self._rel(target)})

    async def delete(self, path: str, *, folder: bool = False) -> None:
        """Datei löschen, mit ``folder=True`` einen leeren Ordner (Scope ``bwsync:delete``).

        Ordner mit Inhalt → ``bwsync-folder-not-empty``; Gelöschtes landet im Papierkorb von bwSync&Share.
        """
        await self._t.send("DELETE", self._folder(path) if folder else self._path(path))


class NotenClient:
    def __init__(self, transport: Transport) -> None:
        self._t = transport

    async def list_my_grades(self, *, semester: str | None = None) -> GradeList:
        params = {"semester": semester} if semester else None
        data = await self._t.get("/v1/noten/me/grades", params)
        try:
            return GradeList.model_validate(data)
        except ValidationError:
            raise AdapterError(502, "contract-violation", CONTRACT_VIOLATION) from None
