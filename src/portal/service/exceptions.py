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


class AppCreationDisabledError(Exception):
    """Das Anlegen neuer Apps ist nicht eingeschaltet (kein Abschnitt ``app_creation`` in der Konfiguration)."""

    def __init__(self) -> None:
        """Konstruktor ohne Parameter."""
        super().__init__("Neue Apps anlegen ist nicht eingeschaltet")


class NotAllowedError(Exception):
    """Die Person darf keine Apps anlegen: keine der Rollen aus ``app_creation.creator_roles``."""

    def __init__(self) -> None:
        """Konstruktor ohne Parameter."""
        super().__init__("Rolle zum Anlegen von Apps fehlt")


class InvalidAppRequestError(Exception):
    """Eingabe zum Anlegen einer App ist ungültig (Slug, Sprache oder GitHub-Name).

    :ivar key: Schlüssel des Fehlertexts in ``messages.de.yml`` (``neue_app.error.<key>``)
    :ivar field: Betroffenes Feld: ``slug``, ``language`` oder ``github_login``
    """

    def __init__(self, key: str, field: str) -> None:
        """:param key: Schlüssel des Fehlertexts
        :param field: Betroffenes Feld
        """
        super().__init__(f"Ungültige Eingabe {field}: {key}")
        self.key: str = key
        self.field: str = field


class SlugTakenError(Exception):
    """Der Name ist vergeben, gesperrt oder das Repository gibt es schon. Es wurde nichts angelegt."""

    def __init__(self, slug: str) -> None:
        """:param slug: Name der App"""
        super().__init__(f"Name vergeben: {slug}")
        self.slug: str = slug


class AppCreationFailedError(Exception):
    """Das Anlegen ist bei einem Schritt gescheitert.

    :ivar step: Name des Schrittes
    :ivar repo: ``konto/name`` des Repositorys, ``None`` vor dem Anlegen
    :ivar url: Adresse des Repositorys, ``None`` vor dem Anlegen
    :ivar created: ``True``, wenn das Repository schon existiert (nichts wird automatisch gelöscht)
    """

    def __init__(self, step: str, *, repo: str | None = None, url: str | None = None, created: bool = False) -> None:
        """:param step: Name des Schrittes
        :param repo: ``konto/name`` des Repositorys
        :param url: Adresse des Repositorys
        :param created: ob das Repository schon existiert
        """
        super().__init__(f"Anlegen gescheitert bei: {step}")
        self.step: str = step
        self.repo: str | None = repo
        self.url: str | None = url
        self.created: bool = created
