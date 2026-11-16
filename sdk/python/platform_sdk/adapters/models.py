"""Datenmodelle nach den OpenAPI-Dateien des Adapter-Dienstes (05 §4). Streng: unbekannte Felder sind ein Fehler."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

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


class FolderEntry(_Strict):
    """Ein Eintrag eines bwSync-Ordners."""
    name: str = Field(min_length=1, max_length=255, pattern=r"^[^/\\]+$")
    type: Literal["folder", "file"]
    size: int | None = Field(default=None, ge=0)
    modified: datetime | None = None


class Folder(_Strict):
    """Inhalt eines bwSync-Ordners: Ordner zuerst, dann nach Namen (sortiert der Adapter)."""
    path: str = Field(max_length=1024)
    entries: list[FolderEntry] = Field(max_length=1000)
    truncated: bool          # mehr als 1000 Einträge: nur die ersten
    skipped: int = Field(ge=0)  # Namen, die der Adapter nicht verarbeitet (z. B. mit ":"), fehlen
