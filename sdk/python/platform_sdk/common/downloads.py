"""Downloads: sicherer Content-Disposition-Header und Schutz-Header."""

from __future__ import annotations

import unicodedata
from urllib.parse import quote

# Für jede Antwort mit Dateiinhalt: Browser rät keinen Typ, nichts wird zwischengespeichert.
DOWNLOAD_HEADERS = {"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"}


def content_disposition(filename: str) -> str:
    """``attachment`` mit ASCII-Ersatzname (``filename``) und vollem Namen UTF-8-kodiert (``filename*``).

    Anführungszeichen, Backslash und Steuerzeichen werden entfernt; leer → ``download``.
    """
    clean = "".join(c for c in filename if c.isprintable() and c not in '"\\').strip() or "download"
    ascii_name = unicodedata.normalize("NFKD", clean).encode("ascii", "ignore").decode("ascii").strip()
    stem, dot, ext = ascii_name.rpartition(".")
    if not ascii_name or (dot and not stem.strip()):  # z. B. „日本.txt“ -> „download.txt“
        ascii_name = "download" + (dot + ext if dot else "")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(clean, safe='')}"


def download_headers(filename: str) -> dict[str, str]:
    """``Content-Disposition`` plus ``DOWNLOAD_HEADERS``."""
    return {"Content-Disposition": content_disposition(filename), **DOWNLOAD_HEADERS}
