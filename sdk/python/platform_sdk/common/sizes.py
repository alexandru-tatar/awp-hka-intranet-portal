"""Dateigrößen für Anzeigen: „512 B“, „1,2 MB“ (Faktor 1024, deutsches Komma)."""

from __future__ import annotations


def format_size(size: int | None, *, empty: str = "–") -> str:
    """Bytes lesbar; ``None`` (z. B. Ordner) → ``empty``."""
    if size is None:
        return empty
    if size < 1024:
        return f"{size} B"
    value = float(size)
    for unit in ("KB", "MB", "GB", "TB"):
        value /= 1024
        if value < 1024 or unit == "TB":
            break
    return f"{value:.1f} {unit}".replace(".", ",")
