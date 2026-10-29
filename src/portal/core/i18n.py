"""UI-Texte (04 §6): Jeder sichtbare Text kommt aus ``messages.<sprache>.yml``."""

from __future__ import annotations

import string
from pathlib import Path

import yaml


class _Defaults(dict):
    """Wörterbuch, das für fehlende Platzhalter ``{name}`` unverändert stehen lässt."""
    def __missing__(self, key: str) -> str:
        """Platzhalter unverändert zurückgeben.

        :param key: Name des fehlenden Platzhalters
        :return: ``{key}``
        :rtype: str
        """
        return "{" + key + "}"


class Messages:
    """Zugriff auf die UI-Texte; ein Aufruf liefert den Text zu einem Schlüssel."""
    def __init__(self, path: Path, defaults: dict[str, str] | None = None):
        """Texte aus einer YAML-Datei laden.

        :param path: Pfad zur Datei ``messages.<sprache>.yml``
        :param defaults: Vorgabewerte für Platzhalter, z. B. ``{"kontakt": …}``
        """
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        self._msgs: dict[str, str] = {str(k): str(v) for k, v in data.items()}
        self._defaults = defaults or {}

    def __contains__(self, key: str) -> bool:
        """Ob es zum Schlüssel einen Text gibt.

        :param key: Schlüssel
        :return: ``True``, falls vorhanden
        :rtype: bool
        """
        return key in self._msgs

    def __call__(self, key: str, **kwargs: object) -> str:
        """Text zum Schlüssel liefern und Platzhalter ersetzen.

        :param key: Schlüssel, z. B. ``home.title``
        :param kwargs: Werte für Platzhalter, überschreiben die Vorgabewerte
        :return: Der Text
        :rtype: str
        :raises KeyError: Falls der Schlüssel fehlt
        """
        try:
            template = self._msgs[key]
        except KeyError:
            raise KeyError(f"missing message key {key!r}") from None
        if not any(name for _, name, _, _ in string.Formatter().parse(template)):
            return template
        return template.format_map(_Defaults({**self._defaults, **kwargs}))
