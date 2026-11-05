"""Hält den aktuellen Snapshot; Leser sperren nie, Schreiber tauschen eine Referenz aus (03 §2.2)."""

from __future__ import annotations

import asyncio
import dataclasses
import threading
from types import MappingProxyType
from typing import Hashable

from loguru import logger

from .models import AppView, Snapshot
from .sources import RegistrySource


class Registry:
    """Speicher des aktuellen Snapshots der Apps."""
    def __init__(self, source: RegistrySource, *, keep_status: bool = False):
        """Konstruktor mit Quelle; der Snapshot ist zunächst leer.

        :param source: Quelle der App-Daten
        :param keep_status: ``True``, wenn der Prober den Status setzt. Beim Neuladen behält eine App dann Status und
            letzte Prüfung, solange ihre Registrierung (Manifest und Zeitpunkt der Bereitstellung) gleich geblieben ist.
            Bei ``False`` gilt immer der Status aus der Quelle.
        """
        self._source = source
        self._keep_status = keep_status
        self._lock = threading.Lock()
        self._snapshot = Snapshot(version=0, apps=MappingProxyType({}))
        self._fingerprint: Hashable = None

    def snapshot(self) -> Snapshot:
        """Aktuellen Snapshot liefern.

        :return: Der Snapshot
        :rtype: Snapshot
        """
        return self._snapshot

    def reload(self) -> Snapshot:
        """Quelle neu laden und den Snapshot austauschen.

        :return: Der neue Snapshot
        :rtype: Snapshot
        """
        fingerprint = self._source.fingerprint()
        apps = self._source.load()
        with self._lock:
            if self._keep_status:
                apps = {slug: self._carry_over(self._snapshot.apps.get(slug), app) for slug, app in apps.items()}
            self._snapshot = Snapshot(version=self._snapshot.version + 1, apps=MappingProxyType(apps))
            self._fingerprint = fingerprint
        logger.info("snapshot_swapped version={} apps={}", self._snapshot.version, len(apps))
        return self._snapshot

    def refresh(self) -> Snapshot:
        """Nur neu laden, wenn sich die Quelle seit dem letzten Laden geändert hat.

        :return: Der aktuelle Snapshot
        :rtype: Snapshot
        """
        if self._source.fingerprint() != self._fingerprint:
            return self.reload()
        return self._snapshot

    def set_status(self, app: AppView, status: str, last_probe_at: str | None) -> bool:
        """Status einer App setzen, die der Prober gerade geprüft hat.

        Der Snapshot wird ausgetauscht, die Leser sehen entweder den alten oder den neuen Stand. Hat sich die
        Registrierung der App seit der Prüfung geändert oder ist die App weg, passiert nichts.

        :param app: Die geprüfte Ansicht aus dem Snapshot
        :param status: Neuer Status
        :param last_probe_at: Zeitpunkt der Prüfung für die Anzeige
        :return: ``True``, falls der Status gesetzt wurde
        :rtype: bool
        """
        with self._lock:
            current = self._snapshot.apps.get(app.slug)
            if current is None or not current.same_registration(app):
                return False
            apps = dict(self._snapshot.apps)
            apps[app.slug] = dataclasses.replace(current, status=status, last_probe_at=last_probe_at)
            self._snapshot = Snapshot(version=self._snapshot.version + 1, apps=MappingProxyType(apps))
        return True

    async def watch(self, interval_seconds: float) -> None:
        """Die Quelle regelmäßig auf Änderungen prüfen, bis die Aufgabe abgebrochen wird.

        So erscheint eine neu eingespielte App ohne Neustart des Portals. Ein Fehler beim Laden wird protokolliert,
        der letzte gute Snapshot bleibt.

        :param interval_seconds: Abstand der Prüfungen
        """
        while True:
            await asyncio.sleep(interval_seconds)
            try:
                self.refresh()
            except Exception:
                logger.exception("registry_refresh_failed")

    @staticmethod
    def _carry_over(old: AppView | None, new: AppView) -> AppView:
        """Status und letzte Prüfung der alten Ansicht übernehmen, falls die Registrierung gleich ist.

        :param old: Ansicht im bisherigen Snapshot oder ``None``
        :param new: Frisch geladene Ansicht
        :return: ``new``, mit Status und Prüfzeit von ``old`` bei gleicher Registrierung
        :rtype: AppView
        """
        if old is None or not old.same_registration(new):
            return new
        return dataclasses.replace(new, status=old.status, last_probe_at=old.last_probe_at)
