"""DTO-Klassen für Apps (Service-Schicht)."""

from __future__ import annotations

from dataclasses import dataclass

from ..registry import AppView


@dataclass(eq=False, slots=True, kw_only=True)
class AppDTO:
    """DTO-Klasse für App-Daten (Service-Schicht)."""

    slug: str
    name: str
    category: str
    menu_label: str
    menu_icon: str
    version: str
    status: str
    last_probe_at: str | None
    last_deployed_at: str | None
    path: str

    def __init__(self, app: AppView) -> None:
        """Initialisierung von AppDTO durch ein AppView-Objekt der Registry.

        :param app: AppView-Objekt aus dem Registry-Snapshot
        """
        self.slug = app.slug
        self.name = app.name
        self.category = app.category
        self.menu_label = app.menu_label
        self.menu_icon = app.menu_icon
        self.version = app.version
        self.status = app.status
        self.last_probe_at = app.last_probe_at
        self.last_deployed_at = app.last_deployed_at
        self.path = app.path


@dataclass(eq=False, slots=True, kw_only=True)
class NavGroupDTO:
    """Eine Menü-Kategorie mit ihren Apps."""

    category: str
    items: tuple[AppDTO, ...]
