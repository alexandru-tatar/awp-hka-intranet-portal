"""Zusätzliche Rollen je Subject (``grants.yml``), lesen und von der Verwaltungsseite ändern."""

from __future__ import annotations

import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Iterator

import yaml

from ..registry.registration import atomic_write

HEADER = (
    "# Zusätzliche Rollen je Subject (02 §8). `sub` ist das Subject des IdP.\n"
    "# Diese Datei ändert auch die Verwaltungsseite des Portals (/_portal/admin); Kommentare gehen dabei verloren.\n"
)


class GrantStore(Mapping):
    """Die Grants einer Datei als ``{sub: Rollen}``, immer auf dem Stand der Datei.

    Der Role-Mapper liest wie bei einem Dict (``get``). Die Datei wird neu gelesen, sobald sich ihre Änderungszeit
    ändert, auch wenn von Hand bearbeitet. Geänderte Grants gelten ab der nächsten Anmeldung der Person, weil das
    Portal die Rollen beim Login in die Session schreibt.
    """

    def __init__(self, path: Path) -> None:
        """Konstruktor; fehlt die Datei, gibt es keine Grants, und die erste Änderung legt sie an.

        :param path: ``grants.yml``
        """
        self._path = path
        self._lock = threading.Lock()
        self._stamp: int | None = None
        self._grants: dict[str, frozenset[str]] = {}
        self._refresh()

    def __getitem__(self, sub: str) -> frozenset[str]:
        self._refresh()
        return self._grants[sub]

    def __iter__(self) -> Iterator[str]:
        self._refresh()
        return iter(dict(self._grants))

    def __len__(self) -> int:
        self._refresh()
        return len(self._grants)

    def set(self, sub: str, roles: frozenset[str]) -> None:
        """Die Rollen eines Subjects setzen; ohne Rollen entfällt der Eintrag.

        :param sub: Subject des IdP
        :param roles: Zusätzliche Rollen
        :raises OSError: Falls die Datei nicht geschrieben werden kann
        """
        with self._lock:
            self._reload()
            grants = dict(self._grants)
            if roles:
                grants[sub] = frozenset(roles)
            else:
                grants.pop(sub, None)
            self._write(grants)

    def delete(self, sub: str) -> bool:
        """Den Eintrag eines Subjects löschen.

        :param sub: Subject des IdP
        :return: ``True``, falls es einen Eintrag gab
        :rtype: bool
        :raises OSError: Falls die Datei nicht geschrieben werden kann
        """
        with self._lock:
            self._reload()
            if sub not in self._grants:
                return False
            self._write({s: r for s, r in self._grants.items() if s != sub})
            return True

    def _refresh(self) -> None:
        """Neu lesen, falls sich die Datei geändert hat."""
        with self._lock:
            try:
                stamp = self._path.stat().st_mtime_ns
            except FileNotFoundError:
                stamp = -1
            except OSError:
                return  # Datei im Moment nicht lesbar: der letzte Stand gilt
            if stamp != self._stamp:
                self._reload()

    def _reload(self) -> None:
        """Datei lesen (mit gehaltener Sperre)."""
        try:
            raw = yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}
            self._stamp = self._path.stat().st_mtime_ns
        except FileNotFoundError:
            raw, self._stamp = {}, -1
        self._grants = {g["sub"]: frozenset(g.get("roles") or ()) for g in raw.get("grants", ())}

    def _write(self, grants: dict[str, frozenset[str]]) -> None:
        """Datei schreiben (mit gehaltener Sperre).

        :param grants: Neuer Stand
        """
        body = {"grants": [{"sub": sub, "roles": sorted(roles)} for sub, roles in sorted(grants.items())]}
        text = HEADER + (yaml.safe_dump(body, allow_unicode=True, sort_keys=False) if grants else "grants: []\n")
        atomic_write(self._path, text)
        self._grants = grants
        self._stamp = self._path.stat().st_mtime_ns
