"""Noten: Aufrufe des Noten-Adapters (Beschreibung: README.md in diesem Ordner)."""

from __future__ import annotations

from pydantic import ValidationError

from ...errors import AdapterError
from ..transport import CONTRACT_VIOLATION, Transport
from .models import GradeList


class NotenClient:
    def __init__(self, transport: Transport) -> None:
        self._t = transport

    async def list_my_grades(self, *, semester: str | None = None) -> GradeList:
        params = {"semester": semester} if semester else None
        data = await self._t.get("/v1/noten/me/grades", params)
        try:
            return GradeList.model_validate(data)
        except ValidationError:
            raise AdapterError(502, CONTRACT_VIOLATION, "") from None
