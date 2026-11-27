"""DocService: Dokumentation lesen (Seiten, Versionsverlauf, letzte Änderungen, hochgeladene Dateien)."""

from __future__ import annotations

from pathlib import Path
from typing import Final

from loguru import logger

from ..docs import DocNotFoundError, DocStore
from .doc_dto import DocChangeDTO, DocPageDTO, DocVersionDTO, MaintainerDTO, PersonDTO
from .exceptions import NotFoundError

#: Höchstzahl der Einträge auf der Seite „Letzte Änderungen“.
CHANGES_LIMIT: Final = 200


class DocService:
    """Lesender Zugriff auf die Dokumentation."""

    def __init__(self, repo: DocStore) -> None:
        """:param repo: Docs-Speicher"""
        self.repo = repo

    @property
    def writable(self) -> bool:
        """Ob die Dokumentation bearbeitet werden kann.

        :return: ``True`` mit Speicherordner
        :rtype: bool
        """
        return self.repo.writable

    def find_all(self) -> list[DocPageDTO]:
        """Alle Seiten in der Reihenfolge der Navigation.

        :return: Seiten
        :rtype: list[DocPageDTO]
        """
        return [DocPageDTO(p) for p in self.repo.pages()]

    def find_by_slug(self, slug: str) -> DocPageDTO:
        """Eine Seite.

        :param slug: Kurzname
        :return: Seite
        :rtype: DocPageDTO
        :raises NotFoundError: Falls es die Seite nicht gibt
        """
        logger.debug("slug={}", slug)
        try:
            return DocPageDTO(self.repo.page(slug))
        except DocNotFoundError:
            raise NotFoundError(slug) from None

    def find_history(self, slug: str) -> list[DocVersionDTO]:
        """Versionsverlauf einer Seite, die neueste zuerst.

        :param slug: Kurzname
        :return: Versionen
        :rtype: list[DocVersionDTO]
        :raises NotFoundError: Falls es die Seite nie gab
        """
        logger.debug("slug={}", slug)
        try:
            return [DocVersionDTO(v) for v in self.repo.versions(slug)]
        except DocNotFoundError:
            raise NotFoundError(slug) from None

    def find_version(self, slug: str, number: int) -> DocVersionDTO:
        """Eine bestimmte Version einer Seite mit Inhalt.

        :param slug: Kurzname
        :param number: Nummer der Version
        :return: Version
        :rtype: DocVersionDTO
        :raises NotFoundError: Falls es die Version nicht gibt
        """
        logger.debug("slug={} version={}", slug, number)
        try:
            return DocVersionDTO(self.repo.version(slug, number))
        except DocNotFoundError:
            raise NotFoundError(f"{slug}@{number}") from None

    def find_changes(self, limit: int = CHANGES_LIMIT) -> list[DocChangeDTO]:
        """Die letzten Änderungen, die neueste zuerst.

        :param limit: Höchstzahl der Einträge
        :return: Änderungen
        :rtype: list[DocChangeDTO]
        """
        existing: Final = {p.slug for p in self.repo.pages()}
        return [DocChangeDTO(c, exists=c.slug in existing) for c in self.repo.changes(limit)]

    def find_asset(self, name: str) -> Path:
        """Pfad einer hochgeladenen Datei.

        :param name: Dateiname
        :return: Pfad
        :rtype: Path
        :raises NotFoundError: Falls es die Datei nicht gibt
        """
        try:
            return self.repo.asset(name)
        except DocNotFoundError:
            raise NotFoundError(name) from None

    def is_editor(self, sub: str) -> bool:
        """Ob die Verwaltungsseite die Person als Maintainer freigegeben hat.

        :param sub: Subject des IdP
        :return: ``True`` bei einer Freigabe
        :rtype: bool
        """
        return self.repo.is_editor(sub)

    def find_maintainers(self, edit_roles: tuple[str, ...]) -> list[MaintainerDTO]:
        """Alle, die bearbeiten dürfen: Freigaben der Verwaltungsseite und bekannte Personen mit Bearbeitungsrolle.

        Personen mit Rolle aus der Anmeldung kennt das Portal erst, wenn sie es einmal genutzt haben.

        :param edit_roles: Bearbeitungsrollen (``docs.edit_roles``)
        :return: Nach Name sortiert
        :rtype: list[MaintainerDTO]
        """
        people: Final = {p.sub: p for p in self.repo.people()}
        result: dict[str, MaintainerDTO] = {}
        for e in self.repo.editors():
            seen = people.get(e.sub)
            result[e.sub] = MaintainerDTO(
                sub=e.sub, name=seen.name if seen else e.name, added=True, added_by=e.added_by, added_at=e.added_at,
                via_role=bool(seen and set(seen.roles) & set(edit_roles)), last_seen=seen.last_seen if seen else None)
        for p in people.values():
            if p.sub not in result and set(p.roles) & set(edit_roles):
                result[p.sub] = MaintainerDTO(sub=p.sub, name=p.name, via_role=True, added=False, last_seen=p.last_seen)
        return sorted(result.values(), key=lambda m: m.name.lower())

    def find_people(self) -> list[PersonDTO]:
        """Personen, die das Portal schon genutzt haben, nach Name sortiert.

        :return: Personen
        :rtype: list[PersonDTO]
        """
        people = [PersonDTO(sub=p.sub, name=p.name, last_seen=p.last_seen) for p in self.repo.people()]
        return sorted(people, key=lambda p: p.name.lower())
