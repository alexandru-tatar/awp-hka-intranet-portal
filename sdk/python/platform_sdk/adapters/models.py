"""Datenmodelle nach den OpenAPI-Dateien des Adapter-Dienstes (05 §4). Streng: unbekannte Felder sind ein Fehler."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Grade(_Strict):
    module: str = Field(max_length=120)
    semester: str
    grade: str = Field(pattern=r"^([1-4][,.][037]|5[,.]0|bestanden|nicht bestanden)$")
    credits: int | None = Field(default=None, ge=0, le=30)


class GradeList(_Strict):
    items: list[Grade] = Field(max_length=500)
