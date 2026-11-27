"""Docs-Speicher: Seiten, Versionen, Änderungsprotokoll und hochgeladene Dateien als Dateien in einem Ordner.

Aufbau des Ordners (``docs.dir`` in der Konfiguration)::

    pages/<slug>.json            aktueller Stand einer Seite
    versions/<slug>/<n>.json     jede veröffentlichte Version, nie überschrieben
    changes.jsonl                eine Zeile je Änderung (neueste unten)
    order.json                   Reihenfolge der Seiten in der Navigation
    seed.json                    Prüfsumme des Ausgangsstands je Seite, der zuletzt übernommen wurde
    assets/<hash>.<endung>       hochgeladene Bilder und PDFs

Ist der Ordner leer, übernimmt der Speicher beim Start den Ausgangsstand aus ``seed.html`` als Version 1. Ändert sich
``seed.html`` später (neue Fassung im Repository), übernimmt der Start die neue Fassung als neue Version, aber nur für
Seiten, die seit dem letzten Ausgangsstand niemand im Browser bearbeitet hat; neue Seiten aus ``seed.html`` kommen dazu.
Ohne Ordner liest er nur den Ausgangsstand und lässt keine Änderungen zu.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Final

from loguru import logger

from ..registry.registration import atomic_write

SEED_FILE: Final = Path(__file__).resolve().parent / "seed.html"
#: Zeitpunkt und Autor des Ausgangsstands (``Stand`` der ersten Fassung der Dokumentation).
SEED_TS: Final = "2026-11-23T09:00:00+00:00"
SEED_ACTOR: Final = {"name": "Projektteam AWP", "sub": "seed"}

SLUG_RE: Final = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
ASSET_RE: Final = re.compile(r"^[0-9a-f]{20}\.(png|jpg|gif|webp|pdf)$")
#: Seiten-Attribute aus ``<article data-…>``, die der Speicher übernimmt (außer page, title, group).
PAGE_ATTRS: Final = ("level", "time", "tut", "landing")
#: Slugs, die das Portal selbst belegt.
RESERVED: Final = frozenset({"aenderungen"})

_ARTICLE_RE: Final = re.compile(r'^(<article class="page"[^>]*>)\n(.*?)\n^</article>', re.M | re.S)


class DocStoreError(Exception):
    """Basis der Fehler des Docs-Speichers."""


class DocReadOnlyError(DocStoreError):
    """Der Speicher hat keinen Ordner und lässt keine Änderungen zu."""


class DocNotFoundError(DocStoreError):
    """Seite, Version oder Datei gibt es nicht.

    :ivar key: Gesuchter Schlüssel
    """

    def __init__(self, key: str) -> None:
        """:param key: Gesuchter Schlüssel"""
        super().__init__(f"Nicht gefunden: {key}")
        self.key = key


class DocConflictError(DocStoreError):
    """Die Seite wurde seit dem Öffnen des Editors von jemand anderem geändert.

    :ivar current: Aktuelle Seite
    """

    def __init__(self, current: "DocPage") -> None:
        """:param current: Aktuelle Seite"""
        super().__init__(f"Konflikt: {current.slug} ist bei Version {current.version}")
        self.current = current


@dataclass(frozen=True)
class DocPage:
    """Aktueller Stand einer Seite.

    :ivar slug: Kurzname, zugleich Anker in der Adresse (``#slug``)
    :ivar title: Titel in Navigation und Browser-Tab
    :ivar group: Bereich in der Navigation
    :ivar html: Inhalt der Seite (ohne ``<article>``)
    :ivar attrs: Weitere Angaben aus :data:`PAGE_ATTRS`, z. B. ``level``
    :ivar version: Laufende Nummer, beginnt bei 1
    :ivar created_at: Zeitpunkt der ersten Version (ISO 8601, UTC)
    :ivar created_by: Name der Person, die die Seite angelegt hat
    :ivar updated_at: Zeitpunkt der aktuellen Version
    :ivar updated_by: Name der Person, die die aktuelle Version veröffentlicht hat
    """
    slug: str
    title: str
    group: str
    html: str
    attrs: dict[str, str] = field(default_factory=dict)
    version: int = 1
    created_at: str = SEED_TS
    created_by: str = SEED_ACTOR["name"]
    updated_at: str = SEED_TS
    updated_by: str = SEED_ACTOR["name"]


@dataclass(frozen=True)
class DocVersion:
    """Eine veröffentlichte Version einer Seite.

    :ivar slug: Kurzname der Seite
    :ivar version: Nummer der Version
    :ivar title: Titel in dieser Version
    :ivar group: Bereich in dieser Version
    :ivar html: Inhalt in dieser Version
    :ivar attrs: Weitere Angaben in dieser Version
    :ivar ts: Zeitpunkt (ISO 8601, UTC)
    :ivar actor: Name der Person
    :ivar note: Änderungsnotiz, kann leer sein
    :ivar action: ``create``, ``update`` oder ``restore``
    """
    slug: str
    version: int
    title: str
    group: str
    html: str
    attrs: dict[str, str]
    ts: str
    actor: str
    note: str
    action: str


@dataclass(frozen=True)
class DocChange:
    """Ein Eintrag im Änderungsprotokoll.

    :ivar ts: Zeitpunkt (ISO 8601, UTC)
    :ivar slug: Kurzname der Seite
    :ivar title: Titel der Seite zum Zeitpunkt der Änderung
    :ivar version: Version nach der Änderung, ``0`` beim Löschen
    :ivar actor: Name der Person
    :ivar action: ``create``, ``update``, ``restore`` oder ``delete``
    :ivar note: Änderungsnotiz, kann leer sein
    """
    ts: str
    slug: str
    title: str
    version: int
    actor: str
    action: str
    note: str


class DocStore:
    """Liest und schreibt die Dokumentation; alle Schreibzugriffe laufen unter einer Sperre."""

    def __init__(self, directory: Path | None) -> None:
        """Speicher öffnen; ein leerer Ordner bekommt den Ausgangsstand.

        :param directory: Ordner des Speichers oder ``None`` für nur lesend aus ``seed.html``
        """
        self._dir = directory
        self._lock = threading.RLock()
        self._pages: dict[str, DocPage] = {}
        self._order: list[str] = []
        if directory is None:
            for page in parse_seed(SEED_FILE.read_text(encoding="utf-8")):
                self._pages[page.slug] = page
                self._order.append(page.slug)
            return
        for sub in ("pages", "versions", "assets"):
            (directory / sub).mkdir(parents=True, exist_ok=True)
        if not any((directory / "pages").glob("*.json")):
            self._seed()
        self._load()
        self._sync_seed()

    @property
    def writable(self) -> bool:
        """Ob Änderungen möglich sind.

        :return: ``True`` mit Ordner
        :rtype: bool
        """
        return self._dir is not None

    # ── lesen ──────────────────────────────────────────────────────────

    def pages(self) -> list[DocPage]:
        """Alle Seiten in der Reihenfolge der Navigation.

        :return: Seiten
        :rtype: list[DocPage]
        """
        with self._lock:
            return [self._pages[s] for s in self._order if s in self._pages]

    def page(self, slug: str) -> DocPage:
        """Eine Seite.

        :param slug: Kurzname
        :return: Die Seite
        :rtype: DocPage
        :raises DocNotFoundError: Falls es die Seite nicht gibt
        """
        with self._lock:
            try:
                return self._pages[slug]
            except KeyError:
                raise DocNotFoundError(slug) from None

    def versions(self, slug: str) -> list[DocVersion]:
        """Alle Versionen einer Seite, die neueste zuerst.

        :param slug: Kurzname
        :return: Versionen
        :rtype: list[DocVersion]
        :raises DocNotFoundError: Falls es die Seite nie gab
        """
        if self._dir is None:
            page = self.page(slug)
            return [_version_of(page, SEED_ACTOR["name"], "", "create")]
        folder = self._dir / "versions" / slug
        if not SLUG_RE.match(slug) or not folder.is_dir():
            raise DocNotFoundError(slug)
        found = [_read_version(slug, f) for f in folder.glob("*.json")]
        return sorted(found, key=lambda v: v.version, reverse=True)

    def version(self, slug: str, number: int) -> DocVersion:
        """Eine bestimmte Version.

        :param slug: Kurzname
        :param number: Nummer der Version
        :return: Die Version
        :rtype: DocVersion
        :raises DocNotFoundError: Falls es die Version nicht gibt
        """
        for v in self.versions(slug):
            if v.version == number:
                return v
        raise DocNotFoundError(f"{slug}@{number}")

    def changes(self, limit: int = 200) -> list[DocChange]:
        """Die letzten Änderungen, die neueste zuerst.

        :param limit: Höchstzahl der Einträge
        :return: Änderungen
        :rtype: list[DocChange]
        """
        if self._dir is None:
            return [DocChange(p.updated_at, p.slug, p.title, p.version, p.updated_by, "create", "")
                    for p in self.pages()][:limit]
        path = self._dir / "changes.jsonl"
        if not path.exists():
            return []
        rows: list[DocChange] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(DocChange(**json.loads(line)))
            except (ValueError, TypeError):
                logger.warning("docs changes line skipped")
        rows.reverse()
        return rows[:limit]

    def asset(self, name: str) -> Path:
        """Pfad einer hochgeladenen Datei.

        :param name: Dateiname wie beim Hochladen vergeben
        :return: Pfad
        :rtype: Path
        :raises DocNotFoundError: Falls der Name ungültig ist oder die Datei fehlt
        """
        if self._dir is None or not ASSET_RE.match(name):
            raise DocNotFoundError(name)
        path = self._dir / "assets" / name
        if not path.is_file():
            raise DocNotFoundError(name)
        return path

    # ── schreiben ──────────────────────────────────────────────────────

    def create(self, *, title: str, group: str, html: str, attrs: dict[str, str], actor: str, note: str,
               after: str | None = None) -> DocPage:
        """Neue Seite anlegen (Version 1).

        :param title: Titel
        :param group: Bereich
        :param html: Inhalt
        :param attrs: Weitere Angaben
        :param actor: Name der Person
        :param note: Änderungsnotiz
        :param after: Slug, hinter dem die Seite in der Navigation erscheint; ohne Wert am Ende des Bereichs
        :return: Die neue Seite
        :rtype: DocPage
        :raises DocReadOnlyError: Ohne Ordner
        """
        with self._lock:
            directory = self._require_dir()
            slug = self._free_slug(title)
            now = _now()
            page = DocPage(slug=slug, title=title, group=group, html=html, attrs=attrs, version=1,
                           created_at=now, created_by=actor, updated_at=now, updated_by=actor)
            self._write_page(directory, page, actor, note, "create")
            self._insert_order(slug, group, after)
            atomic_write(directory / "order.json", json.dumps(self._order, ensure_ascii=False, indent=1))
            logger.info("docs create slug={} actor={}", slug, actor)
            return page

    def update(self, slug: str, *, base_version: int, title: str, group: str, html: str, attrs: dict[str, str],
               actor: str, note: str) -> DocPage:
        """Neue Version einer Seite veröffentlichen.

        :param slug: Kurzname
        :param base_version: Version, auf der die Bearbeitung beruht
        :param title: Titel
        :param group: Bereich
        :param html: Inhalt
        :param attrs: Weitere Angaben
        :param actor: Name der Person
        :param note: Änderungsnotiz
        :return: Die Seite mit der neuen Version
        :rtype: DocPage
        :raises DocNotFoundError: Falls es die Seite nicht gibt
        :raises DocConflictError: Falls inzwischen eine neuere Version existiert
        :raises DocReadOnlyError: Ohne Ordner
        """
        with self._lock:
            directory = self._require_dir()
            current = self.page(slug)
            if current.version != base_version:
                raise DocConflictError(current)
            page = replace(current, title=title, group=group, html=html, attrs=attrs,
                           version=current.version + 1, updated_at=_now(), updated_by=actor)
            self._write_page(directory, page, actor, note, "update")
            if group != current.group:
                self._order.remove(slug)
                self._insert_order(slug, group, None)
                atomic_write(directory / "order.json", json.dumps(self._order, ensure_ascii=False, indent=1))
            logger.info("docs update slug={} version={} actor={}", slug, page.version, actor)
            return page

    def restore(self, slug: str, number: int, *, actor: str) -> DocPage:
        """Eine frühere Version als neue Version veröffentlichen.

        :param slug: Kurzname
        :param number: Nummer der Version, die wiederhergestellt wird
        :param actor: Name der Person
        :return: Die Seite mit der neuen Version
        :rtype: DocPage
        :raises DocNotFoundError: Falls es Seite oder Version nicht gibt
        :raises DocReadOnlyError: Ohne Ordner
        """
        with self._lock:
            directory = self._require_dir()
            current = self.page(slug)
            old = self.version(slug, number)
            page = replace(current, title=old.title, group=old.group, html=old.html, attrs=dict(old.attrs),
                           version=current.version + 1, updated_at=_now(), updated_by=actor)
            self._write_page(directory, page, actor, f"Version {number} wiederhergestellt", "restore")
            if old.group != current.group:
                self._order.remove(slug)
                self._insert_order(slug, old.group, None)
                atomic_write(directory / "order.json", json.dumps(self._order, ensure_ascii=False, indent=1))
            logger.info("docs restore slug={} from={} actor={}", slug, number, actor)
            return page

    def delete(self, slug: str, *, actor: str) -> None:
        """Seite aus der Navigation entfernen; ihre Versionen bleiben im Ordner erhalten.

        :param slug: Kurzname
        :param actor: Name der Person
        :raises DocNotFoundError: Falls es die Seite nicht gibt
        :raises DocReadOnlyError: Ohne Ordner
        """
        with self._lock:
            directory = self._require_dir()
            page = self.page(slug)
            (directory / "pages" / f"{slug}.json").unlink(missing_ok=True)
            del self._pages[slug]
            if slug in self._order:
                self._order.remove(slug)
            atomic_write(directory / "order.json", json.dumps(self._order, ensure_ascii=False, indent=1))
            self._log(directory, DocChange(_now(), slug, page.title, 0, actor, "delete", ""))
            logger.info("docs delete slug={} actor={}", slug, actor)

    def save_asset(self, data: bytes, extension: str) -> str:
        """Hochgeladene Datei ablegen; gleiche Inhalte bekommen denselben Namen.

        :param data: Inhalt
        :param extension: Endung ohne Punkt (``png``, ``jpg``, ``gif``, ``webp``, ``pdf``)
        :return: Dateiname im Ordner ``assets``
        :rtype: str
        :raises DocReadOnlyError: Ohne Ordner
        """
        directory = self._require_dir()
        name = f"{hashlib.sha256(data).hexdigest()[:20]}.{extension}"
        path = directory / "assets" / name
        if not path.exists():
            tmp = path.with_name(f".{name}.tmp")
            tmp.write_bytes(data)
            tmp.replace(path)
            logger.info("docs asset name={} bytes={}", name, len(data))
        return name

    # ── intern ─────────────────────────────────────────────────────────

    def _require_dir(self) -> Path:
        """Ordner des Speichers.

        :return: Ordner
        :rtype: Path
        :raises DocReadOnlyError: Ohne Ordner
        """
        if self._dir is None:
            raise DocReadOnlyError("Docs-Speicher ist nur lesend")
        return self._dir

    def _free_slug(self, title: str) -> str:
        """Freien Slug aus einem Titel bilden.

        :param title: Titel
        :return: Slug, bei Bedarf mit ``-2``, ``-3`` …
        :rtype: str
        """
        base = slugify(title) or "seite"
        taken = set(self._pages) | RESERVED
        if self._dir is not None:
            taken |= {p.name for p in (self._dir / "versions").iterdir() if p.is_dir()}
        slug, n = base, 2
        while slug in taken:
            slug, n = f"{base[:58]}-{n}", n + 1
        return slug

    def _insert_order(self, slug: str, group: str, after: str | None) -> None:
        """Slug in die Reihenfolge einfügen.

        :param slug: Neuer Slug
        :param group: Bereich der Seite
        :param after: Slug, hinter dem eingefügt wird, oder ``None`` für das Ende des Bereichs
        """
        if after in self._order:
            self._order.insert(self._order.index(after) + 1, slug)
            return
        last = max((i for i, s in enumerate(self._order) if s in self._pages and self._pages[s].group == group),
                   default=None)
        if last is None:
            self._order.append(slug)
        else:
            self._order.insert(last + 1, slug)

    def _write_page(self, directory: Path, page: DocPage, actor: str, note: str, action: str) -> None:
        """Version, aktuellen Stand und Protokollzeile schreiben.

        :param directory: Ordner des Speichers
        :param page: Neuer Stand
        :param actor: Name der Person
        :param note: Änderungsnotiz
        :param action: ``create``, ``update`` oder ``restore``
        """
        folder = directory / "versions" / page.slug
        folder.mkdir(parents=True, exist_ok=True)
        version = _version_of(page, actor, note, action)
        atomic_write(folder / f"{page.version}.json", json.dumps(version.__dict__, ensure_ascii=False))
        atomic_write(directory / "pages" / f"{page.slug}.json", json.dumps(page.__dict__, ensure_ascii=False))
        self._pages[page.slug] = page
        self._log(directory, DocChange(page.updated_at, page.slug, page.title, page.version, actor, action, note))

    @staticmethod
    def _log(directory: Path, change: DocChange) -> None:
        """Zeile an das Änderungsprotokoll anhängen.

        :param directory: Ordner des Speichers
        :param change: Änderung
        """
        with (directory / "changes.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(change.__dict__, ensure_ascii=False) + "\n")

    def _seed(self) -> None:
        """Ausgangsstand aus ``seed.html`` als Version 1 ablegen."""
        directory = self._require_dir()
        pages = parse_seed(SEED_FILE.read_text(encoding="utf-8"))
        for page in pages:
            folder = directory / "versions" / page.slug
            folder.mkdir(parents=True, exist_ok=True)
            version = _version_of(page, SEED_ACTOR["name"], "Ausgangsstand der Dokumentation", "create")
            atomic_write(folder / "1.json", json.dumps(version.__dict__, ensure_ascii=False))
            atomic_write(directory / "pages" / f"{page.slug}.json", json.dumps(page.__dict__, ensure_ascii=False))
        atomic_write(directory / "order.json", json.dumps([p.slug for p in pages], ensure_ascii=False, indent=1))
        atomic_write(directory / "seed.json", json.dumps({p.slug: _digest(p.html) for p in pages}, indent=1))
        change = DocChange(SEED_TS, "start", "Dokumentation", 1, SEED_ACTOR["name"], "create",
                           f"Ausgangsstand der Dokumentation mit {len(pages)} Seiten")
        self._log(directory, change)
        logger.info("docs seeded pages={} dir={}", len(pages), directory)

    def _sync_seed(self) -> None:
        """Neue Fassung von ``seed.html`` übernehmen, ohne Bearbeitungen im Browser zu überschreiben.

        Eine Seite bekommt die neue Fassung als neue Version (Autor „Projektteam AWP“), wenn ihr aktueller Inhalt
        noch genau dem zuletzt übernommenen Ausgangsstand entspricht. Wurde sie im Browser bearbeitet, bleibt sie, wie
        sie ist, und das Log nennt sie. Seiten, die neu in ``seed.html`` stehen, kommen dazu; gelöschte Seiten nicht.
        Ohne ``seed.json`` (Speicher von vor dieser Funktion) gilt Version 1 des Projektteams als Ausgangsstand.
        """
        directory = self._require_dir()
        seed_file = directory / "seed.json"
        applied: dict[str, str] = json.loads(seed_file.read_text(encoding="utf-8")) if seed_file.exists() else {}
        if not seed_file.exists():
            for folder in (directory / "versions").iterdir():
                first = folder / "1.json"
                if first.exists():
                    v1 = _read_version(folder.name, first)
                    if v1.actor == SEED_ACTOR["name"]:
                        applied[folder.name] = _digest(v1.html)
        changed = False
        for seed in parse_seed(SEED_FILE.read_text(encoding="utf-8")):
            new = _digest(seed.html)
            if applied.get(seed.slug) == new:
                continue
            current = self._pages.get(seed.slug)
            if current is None:
                if (directory / "versions" / seed.slug).exists():
                    applied[seed.slug] = new  # gelöscht: nicht wiederbeleben
                    changed = True
                    continue
                now = _now()
                page = replace(seed, created_at=now, created_by=SEED_ACTOR["name"], updated_at=now,
                               updated_by=SEED_ACTOR["name"])
                self._write_page(directory, page, SEED_ACTOR["name"], "Neue Seite aus dem Ausgangsstand", "create")
                self._insert_order(seed.slug, seed.group, None)
                logger.info("docs seed added slug={}", seed.slug)
            elif _digest(current.html) == applied.get(seed.slug):
                page = replace(current, title=seed.title, group=seed.group, html=seed.html, attrs=dict(seed.attrs),
                               version=current.version + 1, updated_at=_now(), updated_by=SEED_ACTOR["name"])
                self._write_page(directory, page, SEED_ACTOR["name"], "Ausgangsstand aktualisiert", "update")
                if seed.group != current.group:
                    self._order.remove(seed.slug)
                    self._insert_order(seed.slug, seed.group, None)
                logger.info("docs seed updated slug={} version={}", seed.slug, page.version)
            else:
                logger.warning("docs seed skipped slug={} reason=edited in browser", seed.slug)
            applied[seed.slug] = new
            changed = True
        if changed or not seed_file.exists():
            atomic_write(directory / "order.json", json.dumps(self._order, ensure_ascii=False, indent=1))
            atomic_write(seed_file, json.dumps(applied, indent=1))

    def _load(self) -> None:
        """Seiten und Reihenfolge aus dem Ordner lesen; Seiten ohne Eintrag in ``order.json`` kommen ans Ende."""
        directory = self._require_dir()
        for path in sorted((directory / "pages").glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                page = DocPage(**raw)
            except (ValueError, TypeError):
                logger.warning("docs page skipped file={}", path.name)
                continue
            self._pages[page.slug] = page
        order_file = directory / "order.json"
        order = json.loads(order_file.read_text(encoding="utf-8")) if order_file.exists() else []
        self._order = [s for s in order if s in self._pages]
        self._order += [s for s in self._pages if s not in self._order]


def slugify(text: str) -> str:
    """Slug aus einem Titel: Kleinbuchstaben, Umlaute ausgeschrieben, Bindestriche.

    :param text: Titel
    :return: Slug, höchstens 60 Zeichen, kann leer sein
    :rtype: str
    """
    s = text.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60].strip("-")


def parse_seed(text: str) -> list[DocPage]:
    """Seiten aus ``seed.html`` lesen (je ``<article class="page" …>`` am Zeilenanfang eine Seite).

    :param text: Inhalt von ``seed.html``
    :return: Seiten in der Reihenfolge der Datei
    :rtype: list[DocPage]
    """
    pages: list[DocPage] = []
    for match in _ARTICLE_RE.finditer(text):
        attrs = _tag_attrs(match.group(1))
        extra = {k: attrs[f"data-{k}"] for k in PAGE_ATTRS if f"data-{k}" in attrs}
        pages.append(DocPage(slug=attrs["data-page"], title=attrs["data-title"], group=attrs["data-group"],
                             html=match.group(2), attrs=extra))
    return pages


def _tag_attrs(tag: str) -> dict[str, str]:
    """Attribute eines einzelnen Start-Tags.

    :param tag: Start-Tag als Text
    :return: Attribute mit aufgelösten Entitäten
    :rtype: dict[str, str]
    """
    found: dict[str, str] = {}

    class _P(HTMLParser):
        def handle_starttag(self, _tag, attrs):
            found.update({k: v or "" for k, v in attrs})

    _P().feed(tag)
    return found


def _version_of(page: DocPage, actor: str, note: str, action: str) -> DocVersion:
    """Version aus dem Stand einer Seite.

    :param page: Seite
    :param actor: Name der Person
    :param note: Änderungsnotiz
    :param action: Art der Änderung
    :return: Version
    :rtype: DocVersion
    """
    return DocVersion(slug=page.slug, version=page.version, title=page.title, group=page.group, html=page.html,
                      attrs=dict(page.attrs), ts=page.updated_at, actor=actor, note=note, action=action)


def _read_version(slug: str, path: Path) -> DocVersion:
    """Version aus einer Datei lesen.

    :param slug: Kurzname
    :param path: Datei ``versions/<slug>/<n>.json``
    :return: Version
    :rtype: DocVersion
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["slug"] = slug
    return DocVersion(**raw)


def _digest(html: str) -> str:
    """Prüfsumme eines Seiteninhalts.

    :param html: Inhalt
    :return: SHA-256 als Hex
    :rtype: str
    """
    return hashlib.sha256(html.encode("utf-8")).hexdigest()


def _now() -> str:
    """Aktueller Zeitpunkt in UTC als ISO 8601 ohne Sekundenbruchteile.

    :return: Zeitpunkt
    :rtype: str
    """
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
