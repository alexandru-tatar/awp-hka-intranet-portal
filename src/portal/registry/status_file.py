"""Statusdatei: Das Portal schreibt den Status jeder App in eine Datei, ``list`` liest sie (HKA-56).

Den Status kennt nur das laufende Portal (``prober.py``). Der Befehl ``python -m portal.registry list`` läuft auf der VM
in einem eigenen Container ohne Netz und kann das Portal nicht fragen. Deshalb schreibt der Prober nach jeder Runde den
Stand atomar in eine JSON-Datei (``registry.status_file``), die der Befehl schreibgeschützt liest.

Die Datei wird geschrieben, wenn sich etwas geändert hat, sonst spätestens alle ``HEARTBEAT_SECONDS``. So zeigt
``written_at``, ob das Portal noch läuft. Abweichung von 03 §4 (``GET /registry/apps``): Datei statt Schnittstelle, wie
die übrige einfache Stufe der Registry. Beim Wechsel auf SQLite entfällt die Datei.

Format::

    {"written_at": "2026-11-08T15:00:00+00:00",
     "apps": {"noten": {"status": "healthy", "version": "1.0.0", "last_probe_at": "2026-11-08 15:00:00 UTC"}}}
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Final

from loguru import logger

from .models import Snapshot
from .registration import atomic_write

HEARTBEAT_SECONDS: Final = 30.0
STALE_AFTER_SECONDS: Final = 120.0


@dataclass(frozen=True)
class StatusReport:
    """Inhalt der Statusdatei.

    :ivar written_at: Zeitpunkt des Schreibens, ``None`` ohne lesbare Datei
    :ivar apps: Je Name ein Objekt mit ``status``, ``version`` und ``last_probe_at``
    """
    written_at: datetime | None = None
    apps: dict[str, dict] = field(default_factory=dict)

    def is_stale(self, now: datetime) -> bool:
        """Ob die Datei fehlt oder zu alt ist, das Portal also vermutlich nicht läuft.

        :param now: Aktueller Zeitpunkt mit Zeitzone
        :return: ``True`` ohne Datei oder bei einem Alter über ``STALE_AFTER_SECONDS``
        :rtype: bool
        """
        return self.written_at is None or (now - self.written_at).total_seconds() > STALE_AFTER_SECONDS


class StatusWriter:
    """Schreibt den Status aus dem Snapshot in die Statusdatei."""

    def __init__(self, path: Path, *, monotonic: Callable[[], float] = time.monotonic,
                 wall: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        """Konstruktor.

        :param path: Statusdatei; der Ordner muss existieren und für das Portal schreibbar sein
        :param monotonic: Uhr für den Abstand zwischen zwei Schreibvorgängen
        :param wall: Uhr für ``written_at``
        """
        self._path = path
        self._monotonic = monotonic
        self._wall = wall
        self._last_apps: dict | None = None
        self._last_at = 0.0

    def write(self, snapshot: Snapshot) -> bool:
        """Den Status schreiben, falls er sich geändert hat oder der letzte Schreibvorgang lange her ist.

        Ein Fehler beim Schreiben wird protokolliert, nicht weitergegeben: Das Menü läuft auch ohne Statusdatei.

        :param snapshot: Aktueller Snapshot der Registry
        :return: ``True``, falls geschrieben wurde
        :rtype: bool
        """
        apps = {slug: {"status": app.status, "version": app.version, "last_probe_at": app.last_probe_at}
                for slug, app in sorted(snapshot.apps.items())}
        now = self._monotonic()
        if apps == self._last_apps and now - self._last_at < HEARTBEAT_SECONDS:
            return False
        document = {"written_at": self._wall().isoformat(timespec="seconds"), "apps": apps}
        try:
            atomic_write(self._path, json.dumps(document, indent=2, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning("status_file_write_failed path={} reason={}", self._path, exc)
            return False
        self._last_apps, self._last_at = apps, now
        return True


def read_status(path: Path | None) -> StatusReport:
    """Die Statusdatei lesen. Fehlt sie oder ist sie kaputt, ist der Bericht leer.

    :param path: Statusdatei oder ``None``, falls keine eingestellt ist
    :return: Der Bericht
    :rtype: StatusReport
    """
    if path is None:
        return StatusReport()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        written_at = datetime.fromisoformat(data["written_at"])
        apps = data["apps"]
    except (OSError, ValueError, KeyError, TypeError):
        return StatusReport()
    if written_at.tzinfo is None or not isinstance(apps, dict):
        return StatusReport()
    return StatusReport(written_at, {k: v for k, v in apps.items() if isinstance(v, dict)})
