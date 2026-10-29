"""AppService: lesende Geschäftslogik für Apps (Menü, Status, Zugriff)."""

from __future__ import annotations

import unicodedata
from typing import Final

from loguru import logger

from ..registry import CATEGORIES, Registry
from .app_dto import AppDTO, NavGroupDTO
from .exceptions import ForbiddenError, LoginRequiredError, NotFoundError, UnavailableError
from .session_dto import SessionDTO

NOT_ROUTED: Final = ("registering", "failed", "retired")


def _sort_key(label: str) -> str:
    # "Ä" sortiert bei "A": ausreichend für deutsche Reihenfolge ohne Locale-Abhängigkeit.
    """Sortierschlüssel für deutsche Reihenfolge ohne Locale: „Ä" sortiert bei „A".

    :param label: Beschriftung
    :return: Schlüssel ohne Akzente in Kleinbuchstaben
    :rtype: str
    """
    return unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode().casefold()


class AppService:
    """Service-Klasse mit Geschäftslogik für Apps."""

    def __init__(self, repo: Registry) -> None:
        """Konstruktor mit abhängiger Registry."""
        self.repo: Registry = repo

    def find_nav_groups(self, roles: frozenset[str]) -> list[NavGroupDTO]:
        """Menübaum für die Rollen: feste Kategorienreihenfolge, Einträge alphabetisch.

        Im Menü stehen nur Apps, die gesund sind und mindestens eine Rolle des Benutzers teilen.

        :param roles: Rollen des angemeldeten Benutzers (leer = niemand angemeldet)
        :return: Kategorien mit Apps, leere Kategorien entfallen
        :rtype: list[NavGroupDTO]
        """
        logger.debug("roles={}", roles)
        apps: Final = [
            app
            for app in self.repo.snapshot().apps.values()
            if app.status == "healthy" and app.visible_to(roles)
        ]
        groups: Final[list[NavGroupDTO]] = []
        for category in CATEGORIES:
            items = sorted(
                (app for app in apps if app.category == category),
                key=lambda app: _sort_key(app.menu_label),
            )
            if items:
                groups.append(
                    NavGroupDTO(category=category, items=tuple(AppDTO(app) for app in items))
                )
        logger.debug("groups={}", groups)
        return groups

    def find_all(self) -> list[AppDTO]:
        """Alle Apps mit Status, alphabetisch nach Name.

        :return: Alle Apps des aktuellen Snapshots
        :rtype: list[AppDTO]
        """
        apps: Final = sorted(
            self.repo.snapshot().apps.values(), key=lambda app: app.name.casefold()
        )
        return [AppDTO(app) for app in apps]

    def find_authorized(self, slug: str, session: SessionDTO | None) -> AppDTO:
        """App zum Slug, falls die Session sie aufrufen darf.

        Entscheidungsreihenfolge wie bei /auth/verify (02 §6): unbekannt → 404, keine Session →
        Login, Rolle → 403, Status → 503. Rolle vor Status, damit Fremde nichts über den Status
        erfahren.

        :param slug: Slug der App
        :param session: Angemeldete Session oder None
        :return: Die App
        :rtype: AppDTO
        :raises NotFoundError: Falls die App unbekannt oder nicht geroutet ist
        :raises LoginRequiredError: Falls keine Session vorhanden ist
        :raises ForbiddenError: Falls keine passende Rolle vorhanden ist
        :raises UnavailableError: Falls die App nicht gesund ist
        """
        logger.debug("slug={}", slug)
        app: Final = self.repo.snapshot().get(slug)
        if app is None or app.status in NOT_ROUTED:
            raise NotFoundError(slug)
        if session is None:
            raise LoginRequiredError
        if not app.visible_to(session.roles):
            raise ForbiddenError(slug)
        if app.status != "healthy":
            raise UnavailableError(slug)
        return AppDTO(app)
