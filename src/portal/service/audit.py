"""AuditLog: wer hat wann welche App angelegt (HKA-82, AK6). Nur Namen und Zeit, nie Token oder Schlüssel."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Callable

from loguru import logger

_FIELDS = ("slug", "repo", "template", "step", "reason")


class AuditLog:
    """Hängt je Ereignis eine JSON-Zeile an eine Datei und schreibt dieselbe Angabe ins Log."""

    def __init__(self, file: Path | None, *, now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        """Konstruktor.

        :param file: JSON-Lines-Datei, ``None`` nur Log
        :param now: Uhr mit Zeitzone, für Tests
        """
        self._file = file
        self._now = now
        self._lock = Lock()

    def record(self, action: str, actor: str, **details: str | None) -> None:
        """Ein Ereignis festhalten.

        :param action: ``app_creation_started``, ``app_created``, ``app_creation_failed`` oder ``app_creation_rejected``
        :param actor: Subject der Person
        :param details: ``slug``, ``repo``, ``template``, ``step``, ``reason``
        :raises OSError: Falls die Datei nicht geschrieben werden kann
        """
        unknown = set(details) - set(_FIELDS)
        if unknown:
            raise ValueError(f"Unbekannte Felder: {sorted(unknown)}")
        entry = {"ts": self._now().isoformat(timespec="seconds"), "actor": actor, "action": action,
                 **{key: value for key, value in details.items() if value is not None}}
        logger.info("{} actor={} {}", action, actor, " ".join(f"{k}={v}" for k, v in entry.items()
                                                                if k not in ("ts", "actor", "action")))
        if self._file is not None:
            with self._lock, self._file.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
