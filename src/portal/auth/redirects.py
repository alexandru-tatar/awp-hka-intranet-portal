"""Ziele nach der Anmeldung (02 §4 Schritt 2)."""

from __future__ import annotations

from urllib.parse import quote

MAX_NEXT_LENGTH = 512
_FORBIDDEN_CHARS = ("\\", "\r", "\n")


def sanitize_next(value: str | None) -> str:
    """Open-Redirect-Schutz für den Zielpfad nach der Anmeldung.

    Erlaubt sind nur ``/`` und Pfade unter ``/apps/`` (relativ, ohne ``//``, ohne Backslash und
    Zeilenumbruch, höchstens 512 Zeichen). Alles andere ergibt ``/``.

    :param value: Gewünschter Zielpfad
    :return: Der geprüfte Pfad oder ``/``
    :rtype: str
    """
    if (
        not value
        or not value.startswith("/")
        or value.startswith("//")
        or any(ch in value for ch in _FORBIDDEN_CHARS)
        or len(value) > MAX_NEXT_LENGTH
    ):
        return "/"
    if value == "/" or value.startswith("/apps/"):
        return value
    return "/"


def login_url(next_path: str) -> str:
    """Adresse der Anmeldung mit Rücksprungziel.

    :param next_path: Pfad, zu dem nach der Anmeldung zurückgekehrt wird
    :return: ``/login?next=…`` mit geprüftem Pfad
    :rtype: str
    """
    return f"/login?next={quote(sanitize_next(next_path), safe='/')}"
