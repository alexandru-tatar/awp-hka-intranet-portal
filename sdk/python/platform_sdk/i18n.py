"""Sprache und Texte des SDK (HKA-101): Seitenrahmen, Abmelde-Dialog, Fehlerseiten und Test-Anmeldung.

Die Texte stehen in ``texts.json`` (in Python und JavaScript byte-gleich). Die Sprache kommt aus ``Accept-Language``; das
Security-Gateway setzt den Header nach der Wahl der Person (Umschalter im Portal). Ohne unterstützte Sprache gilt Deutsch.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Mapping

from .context import current_language

LANGUAGES = ("de", "en")
DEFAULT_LANGUAGE = "de"
MAX_ACCEPT_LANGUAGE_LENGTH = 256

TEXTS: dict[str, dict[str, str]] = json.loads((Path(__file__).parent / "texts.json").read_text(encoding="utf-8"))


def pick_language(accept_language: str | None) -> str:
    """Sprache aus ``Accept-Language`` wählen: die erste unterstützte nach Gewicht, ``en-GB`` zählt als ``en``, sonst ``de``."""
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


def env_language(env: Mapping[str, str] | None = None) -> str:
    """Sprache der Ausgabe von Befehlen (ohne Anfrage): ``PORTAL_LANG`` (``de``/``en``), sonst ``LC_ALL``, ``LC_MESSAGES``, ``LANG``.

    Beginnt die erste gesetzte Variable mit ``en``, gilt Englisch, sonst Deutsch.
    """
    env = os.environ if env is None else env
    explicit = (env.get("PORTAL_LANG") or "").strip().lower()
    if explicit in LANGUAGES:
        return explicit
    for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = (env.get(name) or "").strip().lower()
        if value:
            return "en" if value.split("_")[0].split(".")[0] == "en" else DEFAULT_LANGUAGE
    return DEFAULT_LANGUAGE


def language() -> str:
    """Sprache der laufenden Anfrage (von der Middleware gesetzt), sonst Deutsch."""
    return current_language.get()


def texts() -> dict[str, str]:
    """Alle Texte der Sprache der laufenden Anfrage, für die Vorlagen (``{{ tx.logout }}``)."""
    return TEXTS[language()]


def t(key: str) -> str:
    """Text zu einem Schlüssel in der Sprache der laufenden Anfrage."""
    return TEXTS[language()][key]
