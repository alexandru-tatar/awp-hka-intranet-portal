"""Woher die App-Daten kommen.

``ManifestDirectorySource`` ist der Ersatz für die SQLite-Registry (03 §2) in Entwicklung und Pilot;
die SQLite-Registry wird dasselbe ``RegistrySource`` erfüllen.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Hashable, Protocol

import yaml
from loguru import logger

from .models import STATUSES, AppView
from .validation import ManifestInvalid, ManifestValidator


class RegistrySource(Protocol):
    """Vertrag einer Quelle für App-Daten."""
    def load(self) -> dict[str, AppView]:
        """Alle Apps laden.

        :return: Apps nach Slug
        :rtype: dict[str, AppView]
        """
        ...

    def fingerprint(self) -> Hashable:
        """Fingerabdruck, der sich ändert, sobald :meth:`load` etwas anderes liefern würde.

        :return: Vergleichbarer Wert
        :rtype: Hashable
        """
        ...


class ManifestDirectorySource:
    """Liest ``<manifests_dir>/*.json`` (ein Manifest pro App) und optional eine Statusdatei.

    Der Dateiname ist egal, es zählt der ``slug`` im Manifest. Ungültige oder doppelte Manifeste werden
    protokolliert und übersprungen (die echte Registry lehnt sie beim PUT ab). Die Statusdatei (YAML) hat die
    Form ``{slug: {status, last_probe_at, last_deployed_at}}``; Apps ohne Eintrag sind ``healthy``, solange es
    keinen Prober gibt.
    """

    def __init__(self, manifests_dir: Path, validator: ManifestValidator, state_file: Path | None = None):
        """Konstruktor mit Ordner, Validator und Statusdatei.

        :param manifests_dir: Ordner mit den Manifesten
        :param validator: Prüft jedes Manifest
        :param state_file: Statusdatei, optional
        """
        self.manifests_dir = manifests_dir
        self.state_file = state_file
        self.validator = validator

    def load(self) -> dict[str, AppView]:
        """Alle gültigen Manifeste als Apps laden.

        :return: Apps nach Slug
        :rtype: dict[str, AppView]
        """
        state = self._read_state()
        apps: dict[str, AppView] = {}
        for path in self._manifest_files():
            manifest = self._read_manifest(path)
            if manifest is None:
                continue
            slug = manifest["slug"]
            if slug in apps:
                logger.error("manifest_rejected file={} reason=duplicate slug '{}'", path.name, slug)
                continue
            app = self._app_view(manifest, state.get(slug, {}))
            if app is not None:
                apps[slug] = app
        return apps

    def fingerprint(self) -> tuple:
        """Dateinamen und Änderungszeiten der Manifeste und der Statusdatei.

        :return: Vergleichbarer Wert
        :rtype: tuple
        """
        files = self._manifest_files()
        if self.state_file and self.state_file.exists():
            files.append(self.state_file)
        return tuple((f.name, f.stat().st_mtime_ns) for f in files)

    def _manifest_files(self) -> list[Path]:
        """Manifest-Dateien sortiert auflisten.

        :return: Pfade der ``*.json``-Dateien
        :rtype: list[Path]
        """
        return sorted(self.manifests_dir.glob("*.json"))

    def _read_manifest(self, path: Path) -> dict | None:
        """Ein Manifest lesen und prüfen.

        :param path: Pfad der Datei
        :return: Das Manifest oder ``None``, falls es ungültig ist (wird protokolliert)
        :rtype: dict | None
        """
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            self.validator.validate(manifest)
        except (json.JSONDecodeError, ManifestInvalid) as exc:
            logger.error("manifest_rejected file={} reason={}", path.name, exc)
            return None
        return manifest

    def _read_state(self) -> dict[str, dict]:
        """Die Statusdatei lesen.

        :return: Status je Slug, leer ohne Datei
        :rtype: dict[str, dict]
        """
        if not self.state_file or not self.state_file.exists():
            return {}
        data = yaml.safe_load(self.state_file.read_text(encoding="utf-8")) or {}
        return {slug: (v if isinstance(v, dict) else {"status": v}) for slug, v in data.items()}

    @staticmethod
    def _app_view(manifest: dict, state: dict) -> AppView | None:
        """App aus Manifest und Status bauen.

        :param manifest: Geprüftes Manifest
        :param state: Eintrag der Statusdatei
        :return: Die App oder ``None`` bei unbekanntem Status (wird protokolliert)
        :rtype: AppView | None
        """
        status = state.get("status", "healthy")
        if status not in STATUSES:
            logger.error("state_rejected slug={} reason=unknown status '{}'", manifest["slug"], status)
            return None
        return AppView.from_manifest(
            manifest,
            status=status,
            last_probe_at=state.get("last_probe_at"),
            last_deployed_at=state.get("last_deployed_at"),
        )
