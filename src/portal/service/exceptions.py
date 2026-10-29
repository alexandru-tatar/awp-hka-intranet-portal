"""Fachliche Exceptions der Service-Schicht (keine HTTP-Klassen, Übersetzung in web/errors.py)."""

from __future__ import annotations


class NotFoundError(Exception):
    """Es wurde nichts zum Suchschlüssel gefunden (App-Slug oder Session-ID)."""

    def __init__(self, key: str | None = None) -> None:
        """:param key: Suchschlüssel (App-Slug oder Session-ID)"""
        super().__init__(f"Nicht gefunden: {key}")
        self.key: str | None = key


class LoginRequiredError(Exception):
    """Der Zugriff erfordert eine angemeldete Session."""

    def __init__(self) -> None:
        """Konstruktor ohne Parameter."""
        super().__init__("Anmeldung erforderlich")


class ForbiddenError(Exception):
    """Die Session hat keine der erforderlichen Rollen."""

    def __init__(self, slug: str) -> None:
        """:param slug: Slug der App"""
        super().__init__(f"Rolle fehlt für App: {slug}")
        self.slug: str = slug


class UnavailableError(Exception):
    """Die App ist registriert, aber nicht gesund (healthy)."""

    def __init__(self, slug: str) -> None:
        """:param slug: Slug der App"""
        super().__init__(f"App nicht verfügbar: {slug}")
        self.slug: str = slug


class InvalidCsrfError(Exception):
    """Das CSRF-Token passt nicht zur Session."""

    def __init__(self) -> None:
        """Konstruktor ohne Parameter."""
        super().__init__("CSRF-Token ungültig")


class UnknownUserError(Exception):
    """Der Testbenutzer ist in dev/users.yml nicht vorhanden."""

    def __init__(self, user_id: str) -> None:
        """:param user_id: ID der Testperson"""
        super().__init__(f"Unbekannter Benutzer: {user_id}")
        self.user_id: str = user_id


class LoginFailedError(Exception):
    """Die Anmeldung beim IdP ist fehlgeschlagen; der Grund steht nur im Log, nie im Response."""

    def __init__(self, reason: str) -> None:
        """:param reason: Grund, nur für das Log"""
        super().__init__(f"Anmeldung fehlgeschlagen: {reason}")
        self.reason: str = reason
