"""UI-Texte (04 §6): Jeder sichtbare Text kommt aus ``messages.<sprache>.yml``.

Die Sprache gilt je Anfrage (``current_language``). Die Middleware setzt sie aus dem Cookie ``hka_lang`` oder aus
``Accept-Language`` (``pick_language``); ohne gültige Angabe gilt Deutsch (HKA-101).
"""

from __future__ import annotations

from contextvars import ContextVar
import math
import string
from pathlib import Path
from typing import Final

import yaml

LANGUAGES: Final = ("de", "en")
DEFAULT_LANGUAGE: Final = "de"
LANGUAGE_COOKIE: Final = "hka_lang"
MAX_ACCEPT_LANGUAGE_LENGTH: Final = 256

# Sprache der aktuellen Anfrage; die Middleware setzt sie, ``Messages`` liest sie.
current_language: ContextVar[str] = ContextVar("current_language", default=DEFAULT_LANGUAGE)


def pick_language(cookie: str | None, accept_language: str | None) -> str:
    """Sprache einer Anfrage bestimmen.

    Ein gültiges Cookie gewinnt. Sonst zählt die erste unterstützte Sprache aus ``Accept-Language`` nach ihrem
    Gewicht (``q``); ``en-GB`` zählt als ``en``. Ohne Treffer gilt Deutsch.

    :param cookie: Wert des Cookies ``hka_lang`` oder ``None``
    :param accept_language: Wert des Headers ``Accept-Language`` oder ``None``
    :return: ``de`` oder ``en``
    :rtype: str
    """
    if cookie in LANGUAGES:
        return cookie
    if not accept_language or len(accept_language) > MAX_ACCEPT_LANGUAGE_LENGTH:
        return DEFAULT_LANGUAGE
    ranked: list[tuple[float, int, str]] = []
    for position, item in enumerate(accept_language.split(",")):
        tag, *params = (part.strip() for part in item.split(";"))
        weight = 1.0
        for param in params:
            name, _, value = param.partition("=")
            if name.strip().lower() == "q":
                try:
                    weight = float(value)
                except ValueError:
                    weight = 0.0
                if not math.isfinite(weight):
                    weight = 0.0
        primary = tag.split("-")[0].lower()
        if weight > 0 and primary in LANGUAGES:
            ranked.append((-weight, position, primary))
    return min(ranked)[2] if ranked else DEFAULT_LANGUAGE


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
    """Zugriff auf die UI-Texte; ein Aufruf liefert den Text zu einem Schlüssel in der Sprache der Anfrage."""
    def __init__(self, locales_dir: Path, defaults: dict[str, str | dict[str, str]] | None = None):
        """Die Texte aller Sprachen aus ``messages.<sprache>.yml`` laden.

        :param locales_dir: Ordner mit je einer Datei pro Sprache aus ``LANGUAGES``
        :param defaults: Vorgabewerte für Platzhalter, z. B. ``{"kontakt": …}``; ein Wert ist ein Text oder ein
            Wörterbuch ``{"de": …, "en": …}`` (dann gilt der Text der Anfragesprache, sonst der deutsche)
        """
        self._msgs: dict[str, dict[str, str]] = {}
        for code in LANGUAGES:
            data = yaml.safe_load((locales_dir / f"messages.{code}.yml").read_text(encoding="utf-8")) or {}
            self._msgs[code] = {str(k): str(v) for k, v in data.items()}
        self._defaults = defaults or {}

    @property
    def lang(self) -> str:
        """Sprache der aktuellen Anfrage, für ``<html lang>``.

        :return: ``de`` oder ``en``
        :rtype: str
        """
        return current_language.get()

    def __contains__(self, key: str) -> bool:
        """Ob es zum Schlüssel einen Text gibt (in der Standardsprache).

        :param key: Schlüssel
        :return: ``True``, falls vorhanden
        :rtype: bool
        """
        return key in self._msgs[DEFAULT_LANGUAGE]

    def __call__(self, key: str, **kwargs: object) -> str:
        """Text zum Schlüssel liefern und Platzhalter ersetzen.

        Fehlt der Text in der Sprache der Anfrage, gilt der deutsche (ein Test sorgt dafür, dass das nicht vorkommt).

        :param key: Schlüssel, z. B. ``home.title``
        :param kwargs: Werte für Platzhalter, überschreiben die Vorgabewerte
        :return: Der Text
        :rtype: str
        :raises KeyError: Falls der Schlüssel in keiner Sprache fehlt
        """
        try:
            template = self._msgs[self.lang].get(key) or self._msgs[DEFAULT_LANGUAGE][key]
        except KeyError:
            raise KeyError(f"missing message key {key!r}") from None
        if not any(name for _, name, _, _ in string.Formatter().parse(template)):
            return template
        defaults = {
            name: (value.get(self.lang) or value[DEFAULT_LANGUAGE]) if isinstance(value, dict) else value
            for name, value in self._defaults.items()
        }
        return template.format_map(_Defaults({**defaults, **kwargs}))
