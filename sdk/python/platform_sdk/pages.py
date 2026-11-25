"""Fehlerantworten des SDK: HTML-Seite für Browser, sonst problem+json (06 §4).

Dazu die Standardbehandlung nicht abgefangener Fehler (sdk/README.md, „Fehler: Standard“). Ihre Texte stehen nur
hier, auf der Fehlerseite des Portals (Ausnahme aus Regel 1).
"""

from __future__ import annotations

import json
import logging
import sys
import time
import traceback
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response

from .adapters.transport import BACKEND_TIMEOUT, category
from .context import current_request_id
from .errors import AdapterError
from .layout import Layout

env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"), autoescape=True)

log = logging.getLogger("platform_sdk.errors")
if not log.handlers:  # JSON-Zeilen auf stdout, wie das Zugriffslog
    log.addHandler(logging.StreamHandler(sys.stdout))
    log.setLevel(logging.INFO)
    log.propagate = False

# Titel und Text je Art (domain = fachlich, technical = technisch, call = Aufruf oder Programmierfehler)
FALLBACK_TEXTS = {
    "domain": (
        "Das hat nicht geklappt",
        "Die Aktion war nicht möglich. Bitte gehen Sie zurück, laden Sie die Seite neu und versuchen Sie es erneut.",
    ),
    "technical": (
        "Gerade nicht erreichbar",
        "Der Dienst ist gerade nicht erreichbar. Bitte versuchen Sie es später erneut.",
    ),
    "call": (
        "Fehler in der Anwendung",
        "In dieser Anwendung ist ein Fehler aufgetreten. Wenn das wieder passiert, nennen Sie bitte die Vorgangsnummer.",
    ),
}


def error(
    request: Request,
    status: int,
    title: str,
    detail: str,
    *,
    problem_type: str | None = None,
    request_id: str | None = None,
) -> Response:
    request_id = request_id or current_request_id.get()
    if "text/html" in request.headers.get("accept", ""):
        html = env.get_template("error.html").render(title=title, detail=detail, request_id=request_id)
        return HTMLResponse(html, status_code=status)
    body = {"type": f"urn:hka:problem:{problem_type or status}", "title": title, "status": status, "detail": detail}
    if request_id:
        body["request_id"] = request_id
    return JSONResponse(body, status_code=status, media_type="application/problem+json")


async def error_in_layout(request: Request, layout: Layout, status: int, title: str, detail: str) -> Response:
    """Wie `error`, aber die HTML-Seite steht im Seitenrahmen des Portals (Kopf, Menü, Fuß, Weg zur Startseite).

    Ohne angemeldete Person oder ohne `text/html` gilt `error`; ebenso, wenn der Rahmen nicht gebaut werden kann.
    """
    user = getattr(request.state, "portal_user", None)
    if user is None or "text/html" not in request.headers.get("accept", ""):
        return error(request, status, title, detail)
    try:
        body = env.get_template("error_in_layout.html").render(
            title=title, detail=detail, request_id=current_request_id.get()
        )
        html = await layout.render(title=title, body=body, current="", user=user)
    except Exception as exc:  # die einfache Seite ist besser als ein zweiter Fehler
        log.warning("Fehlerseite im Rahmen nicht möglich, einfache Seite: %s", type(exc).__name__)
        return error(request, status, title, detail)
    return HTMLResponse(html, status_code=status)


def fallback(request: Request, exc: Exception) -> Response:
    """Antwort auf einen Fehler, den die App nicht abgefangen hat. Details nur ins Log, nie in die Antwort."""
    request_id = current_request_id.get() or request.headers.get("x-request-id")
    entry: dict = {"path": request.url.path}
    if isinstance(exc, AdapterError):
        kind = category(exc)
        if kind == "technical":
            status = 504 if exc.type == BACKEND_TIMEOUT else 503
        elif kind == "domain":
            status = exc.status if 400 <= exc.status < 500 else 500
        else:
            status = 500
        entry.update({"category": kind, "type": exc.type, "status": exc.status})
        if kind == "domain":
            entry["hint"] = "Die App behandelt diesen type nicht selbst."
        if kind == "call":
            entry["detail"] = exc.detail
        problem_type = exc.type
    else:
        kind, status, problem_type = "call", 500, None
        entry.update({"category": "other", "error": type(exc).__name__,
                      "stack": "".join(traceback.format_exception(exc))})
    level = "warning" if kind in ("domain", "technical") else "error"
    log.log(
        logging.WARNING if level == "warning" else logging.ERROR,
        json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "level": level,
                    "event": "unhandled-error", "request_id": request_id, **entry}),
    )
    title, text = FALLBACK_TEXTS[kind]
    return error(request, status, title, text, problem_type=problem_type, request_id=request_id)
