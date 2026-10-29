"""Was die UI über eine App weiß: das Lesemodell der Registry (03 §2.2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

CATEGORIES = ("Studium", "Verwaltung", "Kommunikation", "Sonstiges")
STATUSES = ("registering", "healthy", "unhealthy", "failed", "retired")
RESERVED_SLUGS = frozenset({
    "_portal", "admin", "api", "auth", "static", "apps", "portal", "adapters", "gateway",
    "traefik", "redis", "registry", "health", "healthz", "login", "logout", "oidc",
})


@dataclass(frozen=True)
class AppView:
    """Eine registrierte App.

    :ivar slug: Eindeutiger Name, Teil der Adresse ``/apps/<slug>/``
    :ivar name: Anzeigename
    :ivar category: Menükategorie, eine aus ``CATEGORIES``
    :ivar menu_label: Beschriftung im Menü
    :ivar menu_icon: Icon aus der Allow-List des Kits
    :ivar roles: Rollen, die die App sehen dürfen
    :ivar adapters: Benötigte Adapter-Scopes
    :ivar claims: Benötigte Claims
    :ivar version: Version der App
    :ivar status: Eine aus ``STATUSES``
    :ivar last_probe_at: Zeitpunkt der letzten Prüfung
    :ivar last_deployed_at: Zeitpunkt des letzten Deployments
    """
    slug: str
    name: str
    category: str
    menu_label: str
    menu_icon: str
    roles: frozenset[str]
    adapters: tuple[str, ...]
    claims: tuple[str, ...]
    version: str
    status: str
    last_probe_at: str | None = None
    last_deployed_at: str | None = None

    @classmethod
    def from_manifest(cls, manifest: dict, *, status: str, last_probe_at: str | None = None,
                      last_deployed_at: str | None = None) -> "AppView":
        """AppView aus einem geprüften Manifest bauen.

        :param manifest: Manifest, bereits gegen das Schema geprüft
        :param status: Status der App
        :param last_probe_at: Zeitpunkt der letzten Prüfung
        :param last_deployed_at: Zeitpunkt des letzten Deployments
        :return: Die App
        :rtype: AppView
        """
        return cls(
            slug=manifest["slug"],
            name=manifest["name"],
            category=manifest["category"],
            menu_label=manifest["menu"]["label"],
            menu_icon=manifest["menu"]["icon"],
            roles=frozenset(manifest["roles"]),
            adapters=tuple(manifest.get("adapters", ())),
            claims=tuple(manifest.get("claims", ())),
            version=manifest["version"],
            status=status,
            last_probe_at=last_probe_at,
            last_deployed_at=last_deployed_at,
        )

    @property
    def path(self) -> str:
        """Adresse der App im Portal.

        :return: ``/apps/<slug>/``
        :rtype: str
        """
        return f"/apps/{self.slug}/"

    def visible_to(self, roles: frozenset[str]) -> bool:
        """Ob die App für die Rollen sichtbar ist (mindestens eine gemeinsame Rolle).

        :param roles: Rollen des Benutzers
        :return: ``True``, falls sichtbar
        :rtype: bool
        """
        return bool(self.roles & roles)


@dataclass(frozen=True)
class Snapshot:
    """Unveränderlicher Stand aller Apps.

    :ivar version: Laufende Nummer, steigt bei jedem Laden
    :ivar apps: Apps nach Slug
    """
    version: int
    apps: Mapping[str, AppView] = field(default_factory=dict)

    def get(self, slug: str) -> AppView | None:
        """App zum Slug suchen.

        :param slug: Slug
        :return: Die App oder ``None``
        :rtype: AppView | None
        """
        return self.apps.get(slug)
