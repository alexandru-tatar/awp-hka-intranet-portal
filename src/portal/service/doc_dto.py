"""DTO-Klassen für die Dokumentation (Service-Schicht)."""

from __future__ import annotations

from dataclasses import dataclass

from ..docs import DocChange, DocPage, DocVersion


@dataclass(eq=False, slots=True, kw_only=True)
class DocPageDTO:
    """Eine Seite der Dokumentation mit den Angaben für die Zeile „Zuletzt aktualisiert“."""

    slug: str
    title: str
    group: str
    html: str
    attrs: tuple[tuple[str, str], ...]
    version: int
    created_at: str
    created_by: str
    updated_at: str
    updated_by: str

    def __init__(self, page: DocPage) -> None:
        """Initialisierung aus einer Seite des Docs-Speichers.

        :param page: Seite
        """
        self.slug = page.slug
        self.title = page.title
        self.group = page.group
        self.html = page.html
        self.attrs = tuple(sorted(page.attrs.items()))
        self.version = page.version
        self.created_at = page.created_at
        self.created_by = page.created_by
        self.updated_at = page.updated_at
        self.updated_by = page.updated_by

    def to_json(self, *, with_html: bool = False) -> dict:
        """Als JSON-Objekt für die Schnittstelle.

        :param with_html: ``True`` nimmt den Inhalt mit
        :return: Wörterbuch
        :rtype: dict
        """
        data = {
            "slug": self.slug, "title": self.title, "group": self.group, "attrs": dict(self.attrs),
            "version": self.version, "created_at": self.created_at, "created_by": self.created_by,
            "updated_at": self.updated_at, "updated_by": self.updated_by,
        }
        if with_html:
            data["html"] = self.html
        return data


@dataclass(eq=False, slots=True, kw_only=True)
class DocVersionDTO:
    """Eine Version im Versionsverlauf."""

    slug: str
    version: int
    title: str
    group: str
    html: str
    ts: str
    actor: str
    note: str
    action: str

    def __init__(self, version: DocVersion) -> None:
        """Initialisierung aus einer Version des Docs-Speichers.

        :param version: Version
        """
        self.slug = version.slug
        self.version = version.version
        self.title = version.title
        self.group = version.group
        self.html = version.html
        self.ts = version.ts
        self.actor = version.actor
        self.note = version.note
        self.action = version.action

    def to_json(self, *, with_html: bool = False) -> dict:
        """Als JSON-Objekt für die Schnittstelle.

        :param with_html: ``True`` nimmt den Inhalt mit
        :return: Wörterbuch
        :rtype: dict
        """
        data = {"slug": self.slug, "version": self.version, "title": self.title, "group": self.group,
                "ts": self.ts, "actor": self.actor, "note": self.note, "action": self.action}
        if with_html:
            data["html"] = self.html
        return data


@dataclass(eq=False, slots=True, kw_only=True)
class DocChangeDTO:
    """Ein Eintrag der Seite „Letzte Änderungen“."""

    ts: str
    slug: str
    title: str
    version: int
    actor: str
    action: str
    note: str
    exists: bool

    def __init__(self, change: DocChange, *, exists: bool) -> None:
        """Initialisierung aus einem Eintrag des Änderungsprotokolls.

        :param change: Eintrag
        :param exists: Ob es die Seite noch gibt (sonst ohne Link)
        """
        self.ts = change.ts
        self.slug = change.slug
        self.title = change.title
        self.version = change.version
        self.actor = change.actor
        self.action = change.action
        self.note = change.note
        self.exists = exists
