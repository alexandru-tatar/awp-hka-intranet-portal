"""Clients je System (06 §8)."""

from __future__ import annotations

from pydantic import ValidationError

from ..errors import AdapterError
from .models import GradeList
from .transport import Transport

CONTRACT_VIOLATION = "Das System hat unerwartete Daten geliefert. Bitte versuchen Sie es später noch einmal."


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
