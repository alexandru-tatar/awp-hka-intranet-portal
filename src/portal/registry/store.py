"""Hält den aktuellen Snapshot; Leser sperren nie, Schreiber tauschen eine Referenz aus (03 §2.2)."""

from __future__ import annotations

import threading
from types import MappingProxyType
from typing import Hashable

from loguru import logger

from .models import Snapshot
from .sources import RegistrySource


class Registry:
    """Speicher des aktuellen Snapshots der Apps."""
    def __init__(self, source: RegistrySource):
        """Konstruktor mit Quelle; der Snapshot ist zunächst leer.

        :param source: Quelle der App-Daten
        """
        self._source = source
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
