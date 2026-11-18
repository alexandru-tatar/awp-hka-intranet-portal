"""Zeitpunkte für Anzeigen: Europe/Berlin, deutsches Format („16.11.2026, 14:28“)."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    LOCAL_TIME: ZoneInfo | None = ZoneInfo("Europe/Berlin")
except ZoneInfoNotFoundError:  # ohne Zeitzonendaten im Image: UTC (mit Kennzeichen)
    LOCAL_TIME = None


def format_datetime(value: datetime | None, *, empty: str = "–") -> str:
    """``TT.MM.JJJJ, HH:MM`` in Berliner Zeit; ohne Zeitzone gilt UTC; ``None`` → ``empty``."""
    if value is None:
        return empty
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    if LOCAL_TIME is None:
        return value.astimezone(UTC).strftime("%d.%m.%Y, %H:%M UTC")
    return value.astimezone(LOCAL_TIME).strftime("%d.%m.%Y, %H:%M")
