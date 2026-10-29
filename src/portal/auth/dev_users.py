"""Testpersonen für die Auswahl beim Login im Dev-Modus (``dev/users.yml``)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class DevUser:
    """Eine Testperson.

    :ivar id: Schlüssel in ``users.yml``
    :ivar name: Anzeigename
    :ivar roles: Rollen der Person
    """
    id: str
    name: str
    roles: tuple[str, ...]


def load_dev_users(path: Path) -> dict[str, DevUser]:
    """Testpersonen aus einer YAML-Datei laden.

    :param path: Pfad zur Datei ``users.yml``
    :return: Testpersonen nach ID
    :rtype: dict[str, DevUser]
    """
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {
        uid: DevUser(id=uid, name=u["name"], roles=tuple(u.get("roles") or ()))
        for uid, u in raw.get("users", {}).items()
    }
