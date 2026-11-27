"""DocWriteService: Dokumentation ändern (Seiten anlegen, bearbeiten, wiederherstellen, löschen, Dateien hochladen).

Jede Änderung wird mit dem Namen der angemeldeten Person und einer optionalen Notiz protokolliert. Das HTML aus dem
Editor wird vor dem Speichern bereinigt (:func:`portal.docs.sanitize_html`).
"""

from __future__ import annotations

import re
from typing import Final

from loguru import logger

from ..docs import DocConflictError, DocNotFoundError, DocReadOnlyError, DocStore, sanitize_html
from ..docs.store import PAGE_ATTRS
from .doc_dto import DocPageDTO
from .exceptions import (
    ConflictError,
    DocsReadOnlyError,
    InvalidInputError,
    NotFoundError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
)
from .session_dto import SessionDTO

#: Pfad, unter dem die hochgeladenen Dateien ausgeliefert werden.
ASSET_PREFIX: Final = "/_portal/docs/assets/"
TITLE_MAX: Final = 120
GROUP_MAX: Final = 60
NOTE_MAX: Final = 300
HTML_MAX: Final = 2 * 1024 * 1024
LEVELS: Final = ("", "Einsteiger", "Fortgeschritten")

#: Erlaubte Formate: Endung und Erkennung am Dateianfang.
_MAGIC: Final = (
    ("png", lambda b: b.startswith(b"\x89PNG\r\n\x1a\n")),
    ("jpg", lambda b: b.startswith(b"\xff\xd8\xff")),
    ("gif", lambda b: b[:6] in (b"GIF87a", b"GIF89a")),
    ("webp", lambda b: b[:4] == b"RIFF" and b[8:12] == b"WEBP"),
    ("pdf", lambda b: b.startswith(b"%PDF-")),
)
_MEDIA: Final = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif", "image/webp": "webp",
                 "application/pdf": "pdf"}
_SPACE: Final = re.compile(r"\s+")


class DocWriteService:
    """Schreibender Zugriff auf die Dokumentation."""

    def __init__(self, repo: DocStore, *, max_upload_bytes: int) -> None:
        """:param repo: Docs-Speicher
        :param max_upload_bytes: Größte erlaubte Datei beim Hochladen
        """
        self.repo = repo
        self.max_upload_bytes = max_upload_bytes

    def create(self, session: SessionDTO, *, title: str, group: str, html: str = "", level: str = "",
               note: str = "", after: str | None = None) -> DocPageDTO:
        """Neue Seite anlegen.

        Ohne Inhalt bekommt die Seite eine Überschrift mit dem Titel und einen Einleitungssatz als Platzhalter.

        :param session: Angemeldete Session (Autor)
        :param title: Titel
        :param group: Bereich in der Navigation
        :param html: Inhalt
        :param level: ``Einsteiger``, ``Fortgeschritten`` oder leer
        :param note: Änderungsnotiz
        :param after: Slug, hinter dem die Seite erscheint
        :return: Die neue Seite
        :rtype: DocPageDTO
        :raises InvalidInputError: Bei leerem oder zu langem Titel, Bereich oder Inhalt
        :raises DocsReadOnlyError: Ohne Speicherordner
        """
        title, group, note = _clean_title(title), _clean_group(group), _clean_note(note)
        if not html.strip():
            html = f"  <h1>{_escape(title)}</h1>\n  <p class=\"lede\">Worum geht es auf dieser Seite?</p>\n"
        content = self._clean_html(html)
        logger.debug("title={} group={}", title, group)
        try:
            page = self.repo.create(title=title, group=group, html=content, attrs=_attrs({}, level),
                                    actor=session.name, note=note or "Seite angelegt", after=after)
        except DocReadOnlyError:
            raise DocsReadOnlyError from None
        return DocPageDTO(page)

    def update(self, session: SessionDTO, slug: str, *, base_version: int, html: str, group: str | None = None,
               level: str | None = None, note: str = "") -> DocPageDTO:
        """Neue Version einer Seite veröffentlichen.

        Der Titel kommt aus der ersten Überschrift ``<h1>`` des Inhalts; ohne ``<h1>`` bleibt er gleich.

        :param session: Angemeldete Session (Autor)
        :param slug: Kurzname
        :param base_version: Version, die im Editor geöffnet wurde
        :param html: Neuer Inhalt
        :param group: Neuer Bereich oder ``None`` für unverändert
        :param level: Neue Stufe oder ``None`` für unverändert
        :param note: Änderungsnotiz
        :return: Seite mit der neuen Version
        :rtype: DocPageDTO
        :raises NotFoundError: Falls es die Seite nicht gibt
        :raises ConflictError: Falls inzwischen jemand anderes eine neuere Version veröffentlicht hat
        :raises InvalidInputError: Bei ungültigen Eingaben
        :raises DocsReadOnlyError: Ohne Speicherordner
        """
        logger.debug("slug={} base_version={}", slug, base_version)
        try:
            current = self.repo.page(slug)
        except DocNotFoundError:
            raise NotFoundError(slug) from None
        content = self._clean_html(html)
        title = _h1_text(content) or current.title
        try:
            page = self.repo.update(
                slug, base_version=base_version, title=_clean_title(title),
                group=_clean_group(group) if group is not None else current.group,
                html=content, attrs=_attrs(current.attrs, level), actor=session.name, note=_clean_note(note))
        except DocConflictError as exc:
            raise ConflictError(exc.current.version, exc.current.updated_by) from None
        except DocReadOnlyError:
            raise DocsReadOnlyError from None
        return DocPageDTO(page)

    def restore(self, session: SessionDTO, slug: str, version: int) -> DocPageDTO:
        """Eine frühere Version als neue Version veröffentlichen.

        :param session: Angemeldete Session (Autor)
        :param slug: Kurzname
        :param version: Nummer der Version
        :return: Seite mit der neuen Version
        :rtype: DocPageDTO
        :raises NotFoundError: Falls es Seite oder Version nicht gibt
        :raises DocsReadOnlyError: Ohne Speicherordner
        """
        logger.debug("slug={} version={}", slug, version)
        try:
            return DocPageDTO(self.repo.restore(slug, version, actor=session.name))
        except DocNotFoundError:
            raise NotFoundError(f"{slug}@{version}") from None
        except DocReadOnlyError:
            raise DocsReadOnlyError from None

    def delete(self, session: SessionDTO, slug: str) -> None:
        """Seite aus der Navigation entfernen; der Versionsverlauf bleibt erhalten.

        Die Startseite ``start`` lässt sich nicht löschen.

        :param session: Angemeldete Session
        :param slug: Kurzname
        :raises NotFoundError: Falls es die Seite nicht gibt
        :raises InvalidInputError: Bei der Startseite
        :raises DocsReadOnlyError: Ohne Speicherordner
        """
        logger.debug("slug={}", slug)
        if slug == "start":
            raise InvalidInputError("docs_start")
        try:
            self.repo.delete(slug, actor=session.name)
        except DocNotFoundError:
            raise NotFoundError(slug) from None
        except DocReadOnlyError:
            raise DocsReadOnlyError from None

    def upload_asset(self, data: bytes, media_type: str) -> str:
        """Bild oder PDF ablegen; das Format wird am Dateianfang geprüft, nicht nur an der Angabe des Browsers.

        :param data: Inhalt
        :param media_type: ``Content-Type`` der Anfrage
        :return: Adresse der Datei, z. B. ``/_portal/docs/assets/<hash>.png``
        :rtype: str
        :raises PayloadTooLargeError: Falls die Datei zu groß ist
        :raises UnsupportedMediaTypeError: Falls das Format nicht erlaubt ist oder nicht zum Inhalt passt
        :raises InvalidInputError: Bei leerer Datei
        :raises DocsReadOnlyError: Ohne Speicherordner
        """
        media = media_type.split(";", 1)[0].strip().lower()
        logger.debug("media={} bytes={}", media, len(data))
        if len(data) > self.max_upload_bytes:
            raise PayloadTooLargeError(self.max_upload_bytes)
        if not data:
            raise InvalidInputError("docs_empty_file")
        expected = _MEDIA.get(media)
        detected = next((ext for ext, test in _MAGIC if test(data)), None)
        if expected is None or detected != expected:
            raise UnsupportedMediaTypeError(media)
        try:
            return ASSET_PREFIX + self.repo.save_asset(data, detected)
        except DocReadOnlyError:
            raise DocsReadOnlyError from None

    def add_editor(self, admin: SessionDTO, sub: str) -> str:
        """Person als Maintainer freigeben (Verwaltungsseite).

        Der Name kommt aus der Liste der bekannten Personen; ohne Eintrag steht dort das Subject.

        :param admin: Session der Person mit Rolle platform-admin
        :param sub: Subject des IdP
        :return: Anzeigename der freigegebenen Person
        :rtype: str
        :raises InvalidInputError: Bei leerem oder zu langem Subject
        :raises DocsReadOnlyError: Ohne Speicherordner
        """
        sub = (sub or "").strip()
        if not sub or len(sub) > 200:
            raise InvalidInputError("maintainer_sub")
        name = next((p.name for p in self.repo.people() if p.sub == sub), sub)
        logger.debug("sub={}", sub)
        try:
            return self.repo.add_editor(sub, name, actor=admin.name).name
        except DocReadOnlyError:
            raise DocsReadOnlyError from None

    def remove_editor(self, admin: SessionDTO, sub: str) -> None:
        """Freigabe als Maintainer entfernen (Verwaltungsseite).

        :param admin: Session der Person mit Rolle platform-admin
        :param sub: Subject des IdP
        :raises NotFoundError: Falls es keine Freigabe gibt
        :raises DocsReadOnlyError: Ohne Speicherordner
        """
        logger.debug("sub={}", sub)
        try:
            self.repo.remove_editor(sub, actor=admin.name)
        except DocNotFoundError:
            raise NotFoundError(sub) from None
        except DocReadOnlyError:
            raise DocsReadOnlyError from None

    def touch_person(self, session: SessionDTO) -> None:
        """Besuch einer Person merken, damit die Verwaltungsseite sie zur Auswahl anbietet.

        :param session: Angemeldete Session
        """
        self.repo.touch_person(session.sub, session.name, tuple(session.roles))

    def _clean_html(self, html: str) -> str:
        """HTML prüfen und bereinigen.

        :param html: HTML aus dem Editor
        :return: Bereinigtes HTML
        :rtype: str
        :raises InvalidInputError: Falls das HTML zu groß ist
        """
        if len(html.encode("utf-8")) > HTML_MAX:
            raise InvalidInputError("docs_too_long")
        return sanitize_html(html, asset_prefix=ASSET_PREFIX)


def _clean_title(title: str) -> str:
    """Titel prüfen.

    :param title: Titel
    :return: Titel ohne doppelte Leerzeichen
    :rtype: str
    :raises InvalidInputError: Bei leerem oder zu langem Titel
    """
    title = _SPACE.sub(" ", title or "").strip()
    if not title or len(title) > TITLE_MAX:
        raise InvalidInputError("docs_title")
    return title


def _clean_group(group: str) -> str:
    """Bereich prüfen.

    :param group: Bereich
    :return: Bereich ohne doppelte Leerzeichen
    :rtype: str
    :raises InvalidInputError: Bei leerem oder zu langem Bereich
    """
    group = _SPACE.sub(" ", group or "").strip()
    if not group or len(group) > GROUP_MAX:
        raise InvalidInputError("docs_group")
    return group


def _clean_note(note: str) -> str:
    """Änderungsnotiz prüfen.

    :param note: Notiz
    :return: Notiz ohne doppelte Leerzeichen
    :rtype: str
    :raises InvalidInputError: Bei zu langer Notiz
    """
    note = _SPACE.sub(" ", note or "").strip()
    if len(note) > NOTE_MAX:
        raise InvalidInputError("docs_note")
    return note


def _attrs(current: dict[str, str], level: str | None) -> dict[str, str]:
    """Seiten-Attribute mit neuer Stufe.

    :param current: Bisherige Attribute
    :param level: Neue Stufe, ``None`` für unverändert
    :return: Attribute
    :rtype: dict[str, str]
    :raises InvalidInputError: Bei unbekannter Stufe
    """
    attrs = {k: v for k, v in current.items() if k in PAGE_ATTRS}
    if level is not None:
        if level not in LEVELS:
            raise InvalidInputError("docs_level")
        attrs.pop("level", None)
        if level:
            attrs["level"] = level
    return attrs


def _h1_text(html: str) -> str:
    """Text der ersten Überschrift ``<h1>``.

    :param html: Bereinigtes HTML
    :return: Text ohne Tags, leer ohne ``<h1>``
    :rtype: str
    """
    from html import unescape

    match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
    if not match:
        return ""
    return _SPACE.sub(" ", unescape(re.sub(r"<[^>]+>", "", match.group(1)))).strip()


def _escape(text: str) -> str:
    """Text für HTML maskieren.

    :param text: Text
    :return: Maskierter Text
    :rtype: str
    """
    from html import escape

    return escape(text, quote=True)
