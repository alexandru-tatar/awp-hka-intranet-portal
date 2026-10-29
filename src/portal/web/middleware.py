"""Verwaltung je Anfrage: Request-ID, Standard-Header und im Dev-Modus das Neuladen der Registry."""

from __future__ import annotations

import re
import secrets
import time

from fastapi import FastAPI, Request, Response
from loguru import logger

from ..core.kit import is_static_path
from .deps import get_portal

REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9-]{1,64}$")
STATIC_CACHE = "public, max-age=31536000, immutable"


def request_id_for(request: Request) -> str:
    """Gültige Request-ID der Anfrage übernehmen, sonst eine neue erzeugen (02 §6).

    :param request: Anfrage; ``X-Request-Id`` muss ``[A-Za-z0-9-]{1,64}`` entsprechen
    :return: Request-ID
    :rtype: str
    """
    incoming = request.headers.get("x-request-id", "")
    return incoming if REQUEST_ID_RE.match(incoming) else secrets.token_hex(8)


def apply_default_headers(request: Request, response: Response) -> None:
    """Standard-Header setzen: Request-ID, Cache-Control, ``nosniff`` und Referrer-Policy.

    Static-Dateien erhalten langes ``immutable``-Caching, alles andere ``no-store``.

    :param request: Anfrage
    :param response: Antwort, wird verändert
    """
    response.headers["X-Request-Id"] = request.state.request_id
    if is_static_path(request.url.path):
        response.headers["Cache-Control"] = STATIC_CACHE
    else:
        response.headers.setdefault("Cache-Control", "no-store")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")


def log_access(request: Request, status: int, started: float) -> None:
    """Zugriffszeile schreiben, im selben Format wie uvicorn, aber mit Request-ID und Dauer.

    Muss innerhalb von ``logger.contextualize(request_id=...)`` aufgerufen werden. Static-Dateien werden nur auf
    Level ``DEBUG`` protokolliert, damit die Seitenaufrufe lesbar bleiben.

    :param request: Anfrage
    :param status: HTTP-Status der Antwort
    :param started: Startzeit von ``time.perf_counter()``
    """
    client = request.client
    peer = f"{client.host}:{client.port}" if client else "-"
    target = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    level = "DEBUG" if is_static_path(request.url.path) else "INFO"
    logger.log(
        level,
        '{} - "{} {} HTTP/{}" {} ({:.1f} ms)',
        peer, request.method, target, request.scope.get("http_version", "1.1"), status,
        (time.perf_counter() - started) * 1000,
    )


def register_middleware(app: FastAPI) -> None:
    """Middleware eintragen.

    Sie vergibt die Request-ID, lädt im Dev-Modus die Registry bei Änderungen neu (außer bei Static-Dateien),
    schreibt die Zugriffszeile (statt ``uvicorn.access``, damit sie die Request-ID trägt) und setzt die Standard-Header.

    :param app: Anwendung
    """
    @app.middleware("http")
    async def portal_request(request: Request, call_next):
        request.state.request_id = request_id_for(request)
        portal = get_portal(request)
        started = time.perf_counter()
        with logger.contextualize(request_id=request.state.request_id):
            if portal.cfg.dev and not is_static_path(request.url.path):
                portal.registry.refresh()  # edits in dev/manifests show up on the next request
            try:
                response = await call_next(request)
            except Exception:
                log_access(request, 500, started)
                raise
            log_access(request, response.status_code, started)
        apply_default_headers(request, response)
        return response
