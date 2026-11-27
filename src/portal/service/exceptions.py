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


class AdminReadOnlyError(Exception):
    """Die Verwaltungsseite darf hier nichts ändern (``registry.admin_write`` aus oder Datei nicht konfiguriert)."""

    def __init__(self) -> None:
        """Konstruktor ohne Parameter."""
        super().__init__("Verwaltung ist nur lesend")


class InvalidInputError(Exception):
    """Eingabe der Verwaltungsseite ist ungültig (keine Rolle, unbekannte Rolle, leeres Subject).

    :ivar key: Schlüssel des Fehlertexts in ``messages.de.yml`` (``admin.error.<key>``)
    """

    def __init__(self, key: str) -> None:
        """:param key: Schlüssel des Fehlertexts"""
        super().__init__(f"Ungültige Eingabe: {key}")
        self.key: str = key


class ConflictError(Exception):
    """Der Datensatz wurde inzwischen geändert (z. B. eine Docs-Seite seit dem Öffnen des Editors).

    :ivar current_version: Aktuelle Version des Datensatzes
    :ivar updated_by: Wer die aktuelle Version veröffentlicht hat
    """

    def __init__(self, current_version: int, updated_by: str) -> None:
        """:param current_version: Aktuelle Version
        :param updated_by: Name der Person, die die aktuelle Version veröffentlicht hat
        """
        super().__init__(f"Konflikt, aktuelle Version {current_version}")
        self.current_version: int = current_version
        self.updated_by: str = updated_by


class DocsReadOnlyError(Exception):
    """Die Dokumentation hat keinen Speicherordner (``docs.dir``) und lässt keine Änderungen zu."""

    def __init__(self) -> None:
        """Konstruktor ohne Parameter."""
        super().__init__("Dokumentation ist nur lesend")


class PayloadTooLargeError(Exception):
    """Die hochgeladene Datei ist größer als erlaubt.

    :ivar limit: Erlaubte Größe in Byte
    """

    def __init__(self, limit: int) -> None:
        """:param limit: Erlaubte Größe in Byte"""
        super().__init__(f"Datei größer als {limit} Byte")
        self.limit: int = limit


class UnsupportedMediaTypeError(Exception):
    """Die hochgeladene Datei hat ein Format, das nicht erlaubt ist."""

    def __init__(self, media_type: str) -> None:
        """:param media_type: Angegebener oder erkannter Typ"""
        super().__init__(f"Format nicht erlaubt: {media_type}")
        self.media_type: str = media_type
