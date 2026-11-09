"""Registrierung einer App: Manifest prüfen, Besitzer binden, Manifest ablegen (HKA-53).

Einfache Stufe der Registry (03 §4 bis §6): Statt einer Schnittstelle mit Token legt ein Admin das Manifest auf der VM über
``portal-deploy`` (``python -m portal.registry``) in den Manifest-Ordner. Das Portal lädt den Ordner selbst nach und prüft ``/healthz``
(``prober.py``). Der Besitzer einer App ist das Repository, aus dem sie kommt. Der erste Besitzer eines Namens bleibt
es (TOFU, 03 §6); ein anderes Repository mit demselben Namen wird abgelehnt.

Alles Schreiben ist atomar: erst eine Hilfsdatei, dann ``os.replace``. Wird abgelehnt, bleibt jede Datei unverändert.

Verwalten (HKA-56): ``list`` zeigt alle Apps, ``remove`` legt eine App still (03 §6). Das Manifest wird gelöscht, die
Bindung an den Besitzer bleibt, und ``retired.json`` (neben der Besitzerdatei, ``{slug: Zeitpunkt}``) merkt sich den
Zeitpunkt. Derselbe Besitzer darf den Namen sofort wieder registrieren; ein anderes Repository erst nach
``SLUG_COOLDOWN_DAYS`` Tagen. Alle Zugriffe auf Manifest-Ordner und Besitzer laufen über ``Registrar``, damit eine
spätere SQLite-Registry (03 §3) nur diese Klasse ersetzt.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Final, Iterator

try:
    import fcntl
except ImportError:  # Windows: keine Sperre, die Registrierung läuft dort nur in Tests
    fcntl = None  # type: ignore[assignment]

from .models import CATEGORIES
from .validation import ManifestInvalid, ManifestValidator

MAX_MANIFEST_BYTES: Final = 64 * 1024
OWNER_RE: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9._-]+$")
LOCK_TIMEOUT_SECONDS: Final = 10.0
SLUG_COOLDOWN_DAYS: Final = 90
SLUG_RE: Final = re.compile(r"^[a-z][a-z0-9-]{2,30}$")  # wie ``slug`` in schemas/manifest.schema.json
LINE: Final = "=" * 60


@dataclass(eq=False)
class Rejected(Exception):
    """Die Registrierung wird abgelehnt, mit Fehlercode aus dem Katalog der Pipeline.

    :ivar code: ``PF-nnn``
    :ivar title: Kurztitel
    :ivar what: Was ist passiert
    :ivar why: Warum es wichtig ist
    :ivar todo: Was zu tun ist, ein Schritt je Eintrag
    :ivar details: Technische Details, eine Zeile je Eintrag
    """
    code: str
    title: str
    what: str
    why: str
    todo: list[str]
    details: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return f"{self.code}: {self.what}"

    def render(self) -> str:
        """Den Fehlerblock im Format des Katalogs (``fehlercodes.md``).

        :return: Mehrzeiliger Text
        :rtype: str
        """
        lines = [LINE, f"FEHLER {self.code}  –  {self.title}", f"Was ist passiert:   {self.what}",
                 f"Warum wichtig:      {self.why}"]
        for number, step in enumerate(self.todo, 1):
            lines.append(f"{'Was tun:' if number == 1 else '':<20}{number}. {step}")
        if self.details:
            lines.append("Technische Details:")
            lines += [f"  {line}" for line in self.details]
        lines.append(LINE)
        return "\n".join(lines)


class RegistryError(Exception):
    """Ein Fehler im Betrieb der Registry, den die App nicht beheben kann (kaputte Besitzerdatei, kein Schreibrecht)."""


class NotRegistered(Exception):
    """``remove`` für einen Namen, zu dem keine aktive App gehört (unbekannt oder schon stillgelegt)."""


class InvalidRoles(ValueError):
    """``set_roles`` mit keiner Rolle oder einer Rolle außerhalb des Vokabulars.

    :ivar unknown: Die unbekannten Rollen
    """

    def __init__(self, unknown: list[str]) -> None:
        """:param unknown: Die unbekannten Rollen, oder ein Platzhalter bei leerer Liste"""
        super().__init__(f"Ungültige Rollen: {', '.join(unknown)}")
        self.unknown = unknown


@dataclass(frozen=True)
class Entry:
    """Eine App, wie ``list`` sie zeigt.

    :ivar slug: Name der App
    :ivar owner: Repository des Besitzers, ``None`` bei einem von Hand eingerichteten Manifest
    :ivar version: Version aus dem Manifest, ``None`` bei einer stillgelegten App oder unlesbarer Datei
    :ivar retired_at: Zeitpunkt der Stilllegung, ``None`` bei einer aktiven App
    """
    slug: str
    owner: str | None
    version: str | None
    retired_at: datetime | None = None


def _manifest_invalid(what: str, details: list[str], *, roles: tuple[str, ...] = ()) -> Rejected:
    """Fehler PF-104 bauen.

    :param what: Satz für „Was ist passiert"
    :param details: Technische Details
    :param roles: Erlaubte Rollen, werden unter „Was tun" genannt
    :return: Der Fehler
    :rtype: Rejected
    """
    todo = ["Korrigieren Sie die genannten Stellen in manifest.json."]
    if roles:
        todo.append(f"Erlaubte Rollen: {', '.join(roles)}.")
        todo.append(f"Erlaubte Kategorien: {', '.join(CATEGORIES)}.")
    todo.append("Mehr dazu: Skill „portal\".")
    return Rejected(
        "PF-104", "manifest.json ungültig", what,
        "Ohne gültiges Manifest nimmt das Portal die App nicht ins Menü auf. Der bisherige Menüstand bleibt.",
        todo, details,
    )


def _name_taken(slug: str, what: str, details: list[str]) -> Rejected:
    """Fehler PF-202 bauen: Der Name gehört schon zu einer anderen App.

    :param slug: Name der App
    :param what: Satz für „Was ist passiert"
    :param details: Technische Details
    :return: Der Fehler
    :rtype: Rejected
    """
    return Rejected(
        "PF-202", "Registrierung abgelehnt", what,
        "Ein Name darf nur zu einer App gehören, sonst könnte eine App eine fremde ersetzen.",
        [f"Wählen Sie in manifest.json einen anderen slug als „{slug}\".",
         "Gehört der Name wirklich zu Ihrer App (zum Beispiel nach dem Umbenennen des Repositorys), fragen Sie das "
         "Plattform-Team."],
        details,
    )


def atomic_write(path: Path, text: str) -> None:
    """Eine Datei atomar schreiben: Hilfsdatei im selben Ordner, dann ersetzen. Lesbar für alle.

    :param path: Zieldatei
    :param text: Inhalt
    """
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise


class Registrar:
    """Prüft Manifeste und legt sie im Manifest-Ordner ab."""

    def __init__(self, manifests_dir: Path, owners_file: Path, validator: ManifestValidator,
                 role_vocabulary: tuple[str, ...], *, lock_timeout: float = LOCK_TIMEOUT_SECONDS,
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        """Konstruktor.

        :param manifests_dir: Ordner, aus dem das Portal die Manifeste liest
        :param owners_file: JSON-Datei ``{slug: owner}``; daneben liegt ``retired.json``
        :param validator: Prüft das Manifest wie das Portal selbst
        :param role_vocabulary: Erlaubte Rollen, für die Meldung bei Fehlern
        :param lock_timeout: Sekunden, die auf eine laufende Registrierung gewartet wird
        :param now: Uhr für Stilllegung und Sperrfrist, mit Zeitzone
        """
        self._dir = manifests_dir
        self._owners_file = owners_file
        self._retired_file = owners_file.with_name("retired.json")
        self._validator = validator
        self._roles = role_vocabulary
        self._lock_timeout = lock_timeout
        self._now = now

    def check(self, raw: bytes, owner: str) -> dict:
        """Alles prüfen, was ``register`` prüft, aber nichts schreiben.

        :param raw: Inhalt der manifest.json
        :param owner: Repository im Format ``owner/name``
        :return: Das Manifest
        :rtype: dict
        :raises Rejected: PF-104 bei ungültigem Manifest, PF-202 bei fremdem Besitzer des Namens
        :raises RegistryError: Falls die Besitzerdatei kaputt ist
        """
        manifest = self._parse(raw)
        self._check_name(manifest["slug"], owner, self._read_owners(), self._read_retired())
        return manifest

    def register(self, raw: bytes, owner: str) -> tuple[dict, bool]:
        """Das Manifest prüfen, den Besitzer binden und das Manifest ablegen.

        Das Portal übernimmt die Datei beim nächsten Nachladen und beginnt mit ``registering``.

        :param raw: Inhalt der manifest.json
        :param owner: Repository im Format ``owner/name``
        :return: Das Manifest und ob die App schon registriert war
        :rtype: tuple[dict, bool]
        :raises Rejected: PF-104, PF-202, oder PF-204 bei laufender Registrierung
        :raises RegistryError: Falls die Besitzerdatei kaputt ist oder nicht geschrieben werden kann
        """
        manifest = self._parse(raw)
        slug = manifest["slug"]
        with self._locked():
            owners = self._read_owners()
            retired = self._read_retired()
            self._check_name(slug, owner, owners, retired)
            known = owners.get(slug) == owner and slug not in retired
            try:
                atomic_write(self._owners_file, json.dumps({**owners, slug: owner}, indent=2, sort_keys=True) + "\n")
                atomic_write(self._dir / f"{slug}.json", json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
                if slug in retired:
                    del retired[slug]
                    self._write_retired(retired)
            except OSError as exc:
                raise RegistryError(f"Schreiben nicht möglich: {exc}") from exc
        return manifest, known

    def entries(self) -> list[Entry]:
        """Alle Apps: registrierte, von Hand eingerichtete und stillgelegte, nach Namen sortiert.

        :return: Die Einträge
        :rtype: list[Entry]
        :raises RegistryError: Falls Besitzerdatei oder ``retired.json`` kaputt sind
        """
        owners = self._read_owners()
        retired = self._read_retired()
        versions: dict[str, str | None] = {}
        for path in sorted(self._dir.glob("*.json")):
            data = self._read_json(path)
            slug = data.get("slug") if isinstance(data, dict) else None
            if isinstance(slug, str):
                version = data.get("version")
                versions[slug] = version if isinstance(version, str) else None
        entries = [Entry(slug, owners.get(slug), versions[slug]) for slug in versions]
        entries += [Entry(slug, owners.get(slug), None, retired[slug]) for slug in retired if slug not in versions]
        return sorted(entries, key=lambda entry: entry.slug)

    def remove(self, slug: str, owner: str) -> None:
        """Eine App stilllegen: Manifest löschen, Zeitpunkt in ``retired.json`` merken, Besitzer behalten.

        Das Portal nimmt die App beim nächsten Nachladen (``registry.refresh_seconds``) aus dem Menü.

        :param slug: Name der App
        :param owner: Repository im Format ``owner/name``; muss der Besitzer sein
        :raises NotRegistered: Falls es zu dem Namen keine aktive, registrierte App gibt
        :raises Rejected: PF-202 bei fremdem Besitzer, PF-204 bei laufender Registrierung
        :raises RegistryError: Falls Dateien kaputt sind oder nicht geschrieben werden können
        """
        self._retire(slug, owner)

    def remove_as_admin(self, slug: str) -> None:
        """Eine App als Plattform-Admin stilllegen, ohne den Besitzer zu kennen (Verwaltungsseite).

        Wirkt wie :meth:`remove`; die Bindung an einen Besitzer bleibt, falls es eine gibt. Auch von Hand eingerichtete
        Apps ohne Besitzer lassen sich so entfernen.

        :param slug: Name der App
        :raises NotRegistered: Falls es zu dem Namen keine aktive App gibt
        :raises Rejected: PF-204 bei laufender Registrierung
        :raises RegistryError: Falls Dateien kaputt sind oder nicht geschrieben werden können
        """
        self._retire(slug, None)

    def set_roles(self, slug: str, roles: list[str] | tuple[str, ...] | frozenset[str]) -> None:
        """Die Rollen einer aktiven App ändern: ``roles`` im Manifest ersetzen und erneut prüfen.

        Besitzer und alle anderen Felder bleiben. Registriert die Pipeline das Manifest danach erneut, gilt wieder
        die Liste aus dem Repository der App.

        :param slug: Name der App
        :param roles: Neue Rollen, mindestens eine, alle aus dem Vokabular
        :raises NotRegistered: Falls es zu dem Namen keine aktive App gibt
        :raises InvalidRoles: Falls keine oder eine unbekannte Rolle übergeben wird
        :raises Rejected: PF-204 bei laufender Registrierung
        :raises RegistryError: Falls Dateien kaputt sind oder nicht geschrieben werden können
        """
        wanted = sorted(set(roles))
        unknown = [role for role in wanted if role not in self._roles]
        if not wanted or unknown:
            raise InvalidRoles(unknown or ["(keine Rolle)"])
        with self._locked():
            retired = self._read_retired()
            path = self._path_of(slug)
            if path is None or slug in retired:
                raise NotRegistered(slug)
            manifest = self._read_json(path)
            if not isinstance(manifest, dict):
                raise RegistryError(f"Datei {path} nicht lesbar")
            manifest["roles"] = wanted
            try:
                self._validator.validate(manifest)
            except ManifestInvalid as exc:
                raise RegistryError(f"Manifest {path.name} wäre danach ungültig: {exc}") from exc
            try:
                atomic_write(path, json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
            except OSError as exc:
                raise RegistryError(f"Schreiben nicht möglich: {exc}") from exc

    def _retire(self, slug: str, owner: str | None) -> None:
        """Eine App stilllegen, mit Besitzerprüfung (``owner``) oder ohne (``None``, Plattform-Admin).

        :param slug: Name der App
        :param owner: Erwarteter Besitzer oder ``None``
        :raises NotRegistered: Falls es zu dem Namen keine aktive App gibt
        :raises Rejected: PF-202 bei fremdem Besitzer, PF-204 bei laufender Registrierung
        :raises RegistryError: Falls Dateien kaputt sind oder nicht geschrieben werden können
        """
        with self._locked():
            owners = self._read_owners()
            retired = self._read_retired()
            target = self._dir / f"{slug}.json"
            bound = owners.get(slug)
            if slug in retired or not target.exists() or (owner is not None and bound is None):
                raise NotRegistered(slug)
            if owner is not None and bound != owner:
                raise Rejected(
                    "PF-202", "Entfernen abgelehnt", f"Die App „{slug}\" gehört zu einem anderen Repository.",
                    "Nur der Besitzer darf eine App entfernen, sonst könnte jemand eine fremde App abschalten.",
                    ["Prüfen Sie den Wert von --owner.", "Gehört die App wirklich Ihnen, fragen Sie das Plattform-Team."],
                    [f"slug={slug} angefragt von {owner}, gebunden an ein anderes Repository"],
                )
            try:
                target.unlink()  # zuerst: Scheitert das Merken danach, bleibt der Name trotzdem an den Besitzer gebunden
                self._write_retired({**retired, slug: self._now()})
            except OSError as exc:
                raise RegistryError(f"Schreiben nicht möglich: {exc}") from exc

    def _path_of(self, slug: str) -> Path | None:
        """Die Manifest-Datei zu einem Namen: ``<slug>.json`` oder die Datei, in der dieser ``slug`` steht.

        :param slug: Name der App
        :return: Pfad oder ``None``, falls es keine Datei gibt
        :rtype: Path | None
        """
        target = self._dir / f"{slug}.json"
        if target.exists():
            return target
        return next((path for path in sorted(self._dir.glob("*.json")) if self._slug_of(path) == slug), None)

    def _parse(self, raw: bytes) -> dict:
        """Das Manifest lesen und prüfen (Schema, reservierter Name, Rolle, Adapter).

        :param raw: Inhalt der manifest.json
        :return: Das Manifest
        :rtype: dict
        :raises Rejected: PF-104
        """
        if len(raw) > MAX_MANIFEST_BYTES:
            raise _manifest_invalid("Die Datei ist größer als 64 KiB.", [f"{len(raw)} Bytes"])
        try:
            manifest = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise _manifest_invalid("Die Datei ist kein gültiges JSON.", [str(exc)]) from exc
        problems = self._validator.problems(manifest)
        if problems:
            fields = ", ".join(dict.fromkeys(problem.split(":", 1)[0] for problem in problems))
            raise _manifest_invalid(f"Die Datei hält die Regeln der Plattform nicht ein. Betroffen: {fields}.",
                                    problems, roles=self._roles)
        return manifest

    def _check_name(self, slug: str, owner: str, owners: dict[str, str], retired: dict[str, datetime]) -> None:
        """Prüfen, ob das Repository den Namen verwenden darf.

        Ein fremdes Repository darf den Namen einer stillgelegten App nach ``SLUG_COOLDOWN_DAYS`` Tagen übernehmen.

        :param slug: Name der App
        :param owner: Repository im Format ``owner/name``
        :param owners: Bisherige Besitzer je Name
        :param retired: Zeitpunkt der Stilllegung je Name
        :raises Rejected: PF-202, falls der Name zu einem anderen Repository gehört, in einer zweiten Datei vorkommt
            oder von Hand eingerichtet wurde
        """
        bound = owners.get(slug)
        if bound is not None and bound != owner:
            retired_at = retired.get(slug)
            if retired_at is None:
                raise _name_taken(slug, f"Der Name „{slug}\" gehört zu einem anderen Repository.",
                                  [f"slug={slug} angefragt von {owner}, gebunden an ein anderes Repository"])
            free_at = retired_at + timedelta(days=SLUG_COOLDOWN_DAYS)
            if self._now() < free_at:
                raise _name_taken(
                    slug, f"Der Name „{slug}\" gehörte zu einer stillgelegten App und ist noch gesperrt.",
                    [f"slug={slug} stillgelegt am {retired_at:%d.%m.%Y}, frei für andere Repositorys ab "
                     f"{free_at:%d.%m.%Y} ({SLUG_COOLDOWN_DAYS} Tage)"],
                )
        target = self._dir / f"{slug}.json"
        for path in sorted(self._dir.glob("*.json")):
            if path != target and self._slug_of(path) == slug:
                raise _name_taken(slug, f"Der Name „{slug}\" steht schon in einer anderen Manifest-Datei.",
                                  [f"Datei {path.name}"])
        if bound is None and target.exists():
            raise _name_taken(slug, f"Der Name „{slug}\" ist von Hand eingerichtet und hat keinen Besitzer.",
                              [f"Datei {target.name} ohne Eintrag in der Besitzerdatei"])

    @staticmethod
    def _read_json(path: Path) -> object:
        """Eine JSON-Datei lesen, ohne sie zu prüfen.

        :param path: Pfad der Datei
        :return: Der Inhalt oder ``None``, falls die Datei nicht lesbar ist
        :rtype: object
        """
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    @classmethod
    def _slug_of(cls, path: Path) -> str | None:
        """Der ``slug`` einer Manifest-Datei, ohne sie zu prüfen.

        :param path: Pfad der Datei
        :return: Der Name oder ``None``, falls die Datei nicht lesbar ist
        :rtype: str | None
        """
        data = cls._read_json(path)
        return data.get("slug") if isinstance(data, dict) else None

    def _read_retired(self) -> dict[str, datetime]:
        """``retired.json`` lesen.

        :return: Zeitpunkt der Stilllegung je Name, leer ohne Datei
        :rtype: dict[str, datetime]
        :raises RegistryError: Falls die Datei nicht die Form ``{name: Zeitpunkt mit Zeitzone}`` hat
        """
        if not self._retired_file.exists():
            return {}
        try:
            data = json.loads(self._retired_file.read_text(encoding="utf-8"))
            result = {slug: datetime.fromisoformat(value) for slug, value in data.items()}
        except (OSError, ValueError, AttributeError, TypeError) as exc:
            raise RegistryError(f"Datei {self._retired_file} nicht lesbar: {exc}") from exc
        if any(value.tzinfo is None for value in result.values()):
            raise RegistryError(f"Datei {self._retired_file}: Zeitpunkt ohne Zeitzone")
        return result

    def _write_retired(self, retired: dict[str, datetime]) -> None:
        """``retired.json`` atomar schreiben.

        :param retired: Zeitpunkt der Stilllegung je Name
        :raises OSError: Falls nicht geschrieben werden kann
        """
        text = json.dumps({slug: moment.isoformat(timespec="seconds") for slug, moment in retired.items()},
                          indent=2, sort_keys=True)
        atomic_write(self._retired_file, text + "\n")

    def _read_owners(self) -> dict[str, str]:
        """Die Besitzerdatei lesen.

        :return: Besitzer je Name, leer ohne Datei
        :rtype: dict[str, str]
        :raises RegistryError: Falls die Datei kein Objekt aus Texten ist
        """
        if not self._owners_file.exists():
            return {}
        try:
            data = json.loads(self._owners_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RegistryError(f"Besitzerdatei {self._owners_file} nicht lesbar: {exc}") from exc
        if not isinstance(data, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in data.items()):
            raise RegistryError(f"Besitzerdatei {self._owners_file} hat nicht die Form {{name: repository}}")
        return data

    @contextlib.contextmanager
    def _locked(self) -> Iterator[None]:
        """Die Registrierung sperren. Wartet bis ``lock_timeout`` auf eine laufende.

        :raises Rejected: PF-204, falls die Sperre nicht frei wird
        :raises RegistryError: Falls die Sperrdatei nicht angelegt werden kann
        """
        if fcntl is None:
            yield
            return
        try:
            handle = open(self._owners_file.with_name(self._owners_file.name + ".lock"), "a")
        except OSError as exc:
            raise RegistryError(f"Sperrdatei nicht anlegbar: {exc}") from exc
        with handle:
            deadline = time.monotonic() + self._lock_timeout
            while True:
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise Rejected(
                            "PF-204", "Bereitstellung gesperrt",
                            "Eine andere Registrierung läuft gerade.",
                            "Zwei Registrierungen gleichzeitig könnten sich gegenseitig überschreiben.",
                            ["Warten Sie einige Sekunden, dann starten Sie die Registrierung erneut."],
                        ) from None
                    time.sleep(0.1)
            yield
