"""Fehlerklassen des SDK."""

from __future__ import annotations


class AdapterError(Exception):
    """Fehler einer Schnittstelle (06 §8). `detail` ist deutsch und darf angezeigt werden."""

    def __init__(self, status: int, type: str, detail: str, request_id: str | None = None) -> None:
        super().__init__(f"{status} {type}")
        self.status = status
        self.type = type
        self.detail = detail
        self.request_id = request_id


class VerifyError(Exception):
    """Prüfung der Anmeldung fehlgeschlagen (06 §5). `code` nennt den Grund, nie den Token-Inhalt."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class PortalHTTPError(Exception):
    """401/403 aus dem SDK; wird als deutsche Seite oder problem+json beantwortet."""

    def __init__(self, status: int, title: str, detail: str) -> None:
        super().__init__(title)
        self.status = status
        self.title = title
        self.detail = detail
