"""AdminService: Geschäftslogik der Verwaltungsseite für Plattform-Admins (Apps, Rollen der Apps, Grants)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from loguru import logger

from ..auth.grants import GrantStore
from ..registry import Registry
from ..registry.registration import InvalidRoles, NotRegistered, Registrar, RegistryError
from .exceptions import AdminReadOnlyError, InvalidInputError, NotFoundError
from .session_dto import SessionDTO


@dataclass(frozen=True, slots=True)
class AdminAppDTO:
    """Eine App, wie die Verwaltungsseite sie zeigt.

    :ivar slug: Name der App
    :ivar name: Anzeigename, bei einer stillgelegten App der Name
    :ivar owner: Repository des Besitzers, ``None`` bei von Hand eingerichteten Apps oder ohne ``owners_file``
    :ivar version: Version aus dem Manifest, ``None`` bei einer stillgelegten App
    :ivar status: Status oder ``retired``
    :ivar category: Menükategorie, ``None`` bei einer stillgelegten App
    :ivar roles: Rollen, die die App sehen dürfen
    :ivar retired_at: Zeitpunkt der Stilllegung, sonst ``None``
    """
    slug: str
    name: str
    owner: str | None
    version: str | None
    status: str
    category: str | None
    roles: tuple[str, ...]
    retired_at: str | None = None


@dataclass(frozen=True, slots=True)
class GrantDTO:
    """Zusätzliche Rollen eines Subjects.

    :ivar sub: Subject des IdP
    :ivar roles: Zusätzliche Rollen, sortiert
    """
    sub: str
    roles: tuple[str, ...]


class AdminService:
    """Liest alles für die Verwaltungsseite und ändert Apps, Rollen und Grants, wenn ``registry.admin_write`` gilt."""

    def __init__(self, registry: Registry, registrar: Registrar | None, grants: GrantStore | None,
                 role_vocabulary: tuple[str, ...], *, writable: bool) -> None:
        """Konstruktor.

        :param registry: Registry mit dem Snapshot der aktiven Apps
        :param registrar: Zugriff auf Manifest-Ordner und Besitzer, ``None`` ohne ``registry.owners_file``
        :param grants: Grants je Subject, ``None`` ohne ``grants_file``
        :param role_vocabulary: Rollen, die vergeben werden dürfen
        :param writable: ``True``, wenn geschrieben werden darf (``registry.admin_write``)
        """
        self._registry = registry
        self._registrar = registrar
        self._grants = grants
        self.role_vocabulary: Final = role_vocabulary
        self.writable: Final = writable

    @property
    def can_manage_apps(self) -> bool:
        """Ob Apps entfernt und ihre Rollen geändert werden dürfen.

        :return: ``True``, falls ein Registrar da ist und ``admin_write`` gilt
        :rtype: bool
        """
        return self.writable and self._registrar is not None

    @property
    def can_manage_grants(self) -> bool:
        """Ob Grants geändert werden dürfen.

        :return: ``True``, falls ``grants_file`` konfiguriert ist und ``admin_write`` gilt
        :rtype: bool
        """
        return self.writable and self._grants is not None

    @property
    def has_grants(self) -> bool:
        """Ob die Grants angezeigt werden können (``grants_file`` konfiguriert).

        :return: ``True``, falls konfiguriert
        :rtype: bool
        """
        return self._grants is not None

    def find_apps(self) -> list[AdminAppDTO]:
        """Alle aktiven und stillgelegten Apps mit Besitzer, Status und Rollen, nach Slug sortiert.

        :return: Die Apps
        :rtype: list[AdminAppDTO]
        :raises RegistryError: Falls Besitzerdatei oder ``retired.json`` kaputt sind
        """
        entries = {entry.slug: entry for entry in self._registrar.entries()} if self._registrar else {}
        snapshot = self._registry.snapshot().apps
        result = [
            AdminAppDTO(
                slug=app.slug, name=app.name, owner=entries[app.slug].owner if app.slug in entries else None,
                version=app.version, status=app.status, category=app.category, roles=tuple(sorted(app.roles)),
            )
            for app in snapshot.values()
        ]
        result += [
            AdminAppDTO(
                slug=entry.slug, name=entry.slug, owner=entry.owner, version=None, status="retired", category=None,
                roles=(), retired_at=f"{entry.retired_at:%d.%m.%Y}",
            )
            for entry in entries.values() if entry.retired_at is not None and entry.slug not in snapshot
        ]
        return sorted(result, key=lambda app: app.slug)

    def find_grants(self) -> list[GrantDTO]:
        """Alle Grants, nach Subject sortiert.

        :return: Die Grants, leer ohne ``grants_file``
        :rtype: list[GrantDTO]
        """
        if self._grants is None:
            return []
        return [GrantDTO(sub, tuple(sorted(roles))) for sub, roles in sorted(self._grants.items())]

    def remove_app(self, slug: str, admin: SessionDTO) -> None:
        """Eine App stilllegen; das Portal nimmt sie sofort aus dem Menü.

        :param slug: Name der App
        :param admin: Plattform-Admin, nur fürs Protokoll
        :raises AdminReadOnlyError: Falls nicht geschrieben werden darf
        :raises NotFoundError: Falls es keine aktive App mit diesem Namen gibt
        :raises Rejected: PF-204 bei laufender Registrierung
        :raises RegistryError: Falls Dateien nicht geschrieben werden können
        """
        registrar = self._app_registrar()
        try:
            registrar.remove_as_admin(slug)
        except NotRegistered:
            raise NotFoundError(slug) from None
        self._registry.reload()
        logger.info("admin_action action=remove_app slug={} admin={}", slug, admin.sub)

    def set_app_roles(self, slug: str, roles: list[str], admin: SessionDTO) -> None:
        """Die Rollen einer App ändern; das Portal zeigt sie sofort.

        :param slug: Name der App
        :param roles: Neue Rollen, mindestens eine, alle aus dem Vokabular
        :param admin: Plattform-Admin, nur fürs Protokoll
        :raises AdminReadOnlyError: Falls nicht geschrieben werden darf
        :raises InvalidInputError: Falls keine oder eine unbekannte Rolle übergeben wird
        :raises NotFoundError: Falls es keine aktive App mit diesem Namen gibt
        :raises Rejected: PF-204 bei laufender Registrierung
        :raises RegistryError: Falls Dateien nicht geschrieben werden können
        """
        registrar = self._app_registrar()
        try:
            registrar.set_roles(slug, roles)
        except InvalidRoles as exc:
            raise InvalidInputError("app_roles_unknown" if exc.unknown != ["(keine Rolle)"] else "app_roles_empty") from exc
        except NotRegistered:
            raise NotFoundError(slug) from None
        self._registry.reload()
        logger.info("admin_action action=set_app_roles slug={} roles={} admin={}", slug, sorted(roles), admin.sub)

    def set_grant(self, sub: str, roles: list[str], admin: SessionDTO) -> None:
        """Die zusätzlichen Rollen eines Subjects setzen; ohne Rollen entfällt der Eintrag.

        Die Rollen gelten ab der nächsten Anmeldung der Person.

        :param sub: Subject des IdP
        :param roles: Zusätzliche Rollen, alle aus dem Vokabular
        :param admin: Plattform-Admin, nur fürs Protokoll
        :raises AdminReadOnlyError: Falls nicht geschrieben werden darf
        :raises InvalidInputError: Falls das Subject leer ist oder eine Rolle unbekannt
        :raises RegistryError: Falls die Datei nicht geschrieben werden kann
        """
        grants = self._grant_store()
        sub = sub.strip()
        if not sub or len(sub) > 200:
            raise InvalidInputError("grant_sub")
        if any(role not in self.role_vocabulary for role in roles):
            raise InvalidInputError("grant_roles_unknown")
        try:
            grants.set(sub, frozenset(roles))
        except OSError as exc:
            raise RegistryError(f"Schreiben nicht möglich: {exc}") from exc
        logger.info("admin_action action=set_grant sub={} roles={} admin={}", sub, sorted(roles), admin.sub)

    def delete_grant(self, sub: str, admin: SessionDTO) -> None:
        """Den Grant eines Subjects löschen.

        :param sub: Subject des IdP
        :param admin: Plattform-Admin, nur fürs Protokoll
        :raises AdminReadOnlyError: Falls nicht geschrieben werden darf
        :raises NotFoundError: Falls es keinen Grant für das Subject gibt
        :raises RegistryError: Falls die Datei nicht geschrieben werden kann
        """
        grants = self._grant_store()
        try:
            found = grants.delete(sub)
        except OSError as exc:
            raise RegistryError(f"Schreiben nicht möglich: {exc}") from exc
        if not found:
            raise NotFoundError(sub)
        logger.info("admin_action action=delete_grant sub={} admin={}", sub, admin.sub)

    def _app_registrar(self) -> Registrar:
        """Registrar, falls Apps geändert werden dürfen.

        :return: Der Registrar
        :rtype: Registrar
        :raises AdminReadOnlyError: Falls nicht
        """
        if not self.can_manage_apps:
            raise AdminReadOnlyError
        assert self._registrar is not None
        return self._registrar

    def _grant_store(self) -> GrantStore:
        """Grant-Speicher, falls Grants geändert werden dürfen.

        :return: Der Speicher
        :rtype: GrantStore
        :raises AdminReadOnlyError: Falls nicht
        """
        if not self.can_manage_grants:
            raise AdminReadOnlyError
        assert self._grants is not None
        return self._grants
