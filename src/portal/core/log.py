"""Logging mit loguru: einheitliche Konsolenzeile, optionale rotierende Logdatei, Level je Logger.

Konsolenzeile::

    2026-10-28T15:30:00.123+01:00 INFO     4711 --- [AnyIO worker th] p.service.app_service    : roles=frozenset() [req=ab12cd]

Zeit mit Zeitzone, Level, Prozess-ID, ``---``, Thread (15 Zeichen), Logger (auf 40 Zeichen gekürzt),
Meldung und die ``request_id`` der Anfrage, dieselbe Nummer wie auf der Fehlerseite.
Meldungen der Standardbibliothek (uvicorn, httpx, redis, ...) laufen über denselben Weg.
"""

from __future__ import annotations

import inspect
import logging
import sys
from typing import Any, Mapping

from loguru import logger

from .config import LoggingConfig

LOGGER_WIDTH = 40

# loguru hängt Zeilenumbruch und Traceback (``{exception}``) selbst an jedes Format an.
_CONSOLE_FORMAT = (
    "<dim>{time:YYYY-MM-DDTHH:mm:ss.SSSZ}</dim> <level>{level: <8}</level> "
    "<magenta>{process}</magenta> <dim>---</dim> <dim>[{thread.name: >15.15}]</dim> "
    "<cyan>{extra[short_name]: <40}</cyan> <dim>:</dim> {message} <dim>[req={extra[request_id]}]</dim>"
)
_FILE_FORMAT = (
    "{time:YYYY-MM-DDTHH:mm:ss.SSSZ} {level: <8} {process} --- [{thread.name: >15.15}] "
    "{extra[short_name]: <40} : {message} [req={extra[request_id]}]"
)


def abbreviate(name: str, width: int = LOGGER_WIDTH) -> str:
    """Loggernamen auf eine Breite kürzen, indem Paketnamen von vorn auf ihren ersten Buchstaben schrumpfen.

    ``portal.service.app_service`` bleibt unverändert, wenn es passt; sonst wird es zu ``p.s.app_service``.
    Der letzte Teil (Modul) bleibt ganz.

    :param name: Vollständiger Name, z. B. ``portal.service.app_service``
    :param width: Höchstbreite
    :return: Der gekürzte Name
    :rtype: str
    """
    parts = name.split(".")
    for i in range(len(parts) - 1):
        if len(".".join(parts)) <= width:
            break
        parts[i] = parts[i][:1]
    return ".".join(parts)[-width:]


def _patch(record: Any) -> None:
    """Jeder Meldung den gekürzten Loggernamen mitgeben.

    :param record: Eintrag von loguru, wird verändert
    """
    record["extra"]["short_name"] = abbreviate(record["name"] or "-")


class InterceptHandler(logging.Handler):
    """Leitet Meldungen der Standardbibliothek (uvicorn, httpx, redis, ...) an loguru weiter."""

    def emit(self, record: logging.LogRecord) -> None:
        """Eine Meldung an loguru übergeben und dabei den Aufrufer des Originals als Quelle behalten.

        :param record: Meldung der Standardbibliothek
        """
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = inspect.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1
        # Der Name des Standard-Loggers (z. B. ``uvicorn.access``, ``httpx``) ersetzt das Modul des Aufrufers:
        # nach ihm richten sich die Level je Logger, und er steht in der Logzeile.
        def rename(entry: Any) -> None:
            entry["name"] = record.name
            entry["extra"]["short_name"] = abbreviate(record.name)

        logger.patch(rename).opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def _filter(default: str, levels: Mapping[str, str]) -> dict[str, str]:
    """Filter für loguru: Mindestlevel je Logger, ``""`` gilt für alle übrigen.

    :param default: Mindestlevel für alle Logger ohne eigene Angabe
    :param levels: Mindestlevel je Logger
    :return: Zuordnung Loggername zu Level
    :rtype: dict[str, str]
    """
    return {"": default, **levels}


def configure_logging(cfg: LoggingConfig) -> None:
    """Logging einrichten: Konsole, optional Logdatei, Standard-Logging umleiten.

    Ersetzt alle bisherigen loguru-Ausgaben. Läuft einmal beim Start (``portal.dev``), nicht beim Erzeugen der
    Anwendung, damit Tests ihre eigenen Ausgaben behalten.

    :param cfg: Einstellungen des Loggings
    """
    logger.remove()
    logger.configure(extra={"request_id": "-", "short_name": "-"}, patcher=_patch)
    logger.add(
        sys.stderr,
        level="TRACE",
        filter=_filter(cfg.console_level, cfg.levels),
        format=_CONSOLE_FORMAT,
        colorize={"auto": None, "always": True, "never": False}[cfg.color],
    )
    if cfg.file is not None:
        logger.add(
            cfg.file,
            level="TRACE",
            filter=_filter(cfg.file_level, cfg.levels),
            format=_FILE_FORMAT,
            rotation=cfg.rotation,
            retention=cfg.retention,
            compression="gz",
            encoding="utf-8",
        )
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        std = logging.getLogger(name)
        std.handlers = []
        std.propagate = True
