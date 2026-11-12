"""Clients je System (06 §8)."""

from __future__ import annotations

from urllib.parse import quote

from pydantic import ValidationError

from ..errors import AdapterError
from .models import GradeList
from .transport import Transport

CONTRACT_VIOLATION = "Das System hat unerwartete Daten geliefert. Bitte versuchen Sie es später noch einmal."


class BwSyncClient:
    def __init__(self, transport: Transport) -> None:
        self._t = transport

    @staticmethod
    def _path(path: str) -> str:
        if (not path or any(c in path for c in "\\%?#:")
                or any(ord(c) < 32 or ord(c) == 127 for c in path)
                or any(part in ("", ".", "..") for part in path.split("/"))):
            raise ValueError("Ein relativer Dateipfad ohne Traversal ist erforderlich.")
        return "/bwsync/files/" + quote(path, safe="/")

    async def upload(self, path: str, data: bytes) -> None:
        await self._t.put_bytes(self._path(path), data)

    async def download(self, path: str, *, max_bytes: int = 10_000_000) -> bytes:
        return await self._t.get_bytes(self._path(path), max_bytes=max_bytes)


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
