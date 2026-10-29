"""Exceptions in Portal-Seiten übersetzen (04 §6): verständlicher Text plus Fehlernummer."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import RedirectResponse, Response
from loguru import logger
from redis.exceptions import RedisError
from starlette.exceptions import HTTPException

from ..auth.redirects import login_url
from ..core.kit import is_static_path
from ..service import (
    ForbiddenError,
    InvalidCsrfError,
    LoginFailedError,
    LoginRequiredError,
    NotFoundError,
    UnavailableError,
    UnknownUserError,
)
from .deps import get_portal, optional_session


def render_error(request: Request, status: int) -> Response:
    """Fehlerseite rendern.

    Eine nicht lesbare Session (Redis nicht erreichbar) gilt als nicht angemeldet, damit die Seite trotzdem erscheint.

    :param request: Anfrage
    :param status: HTTP-Status
    :return: Fehlerseite mit diesem Status
    :rtype: Response
    """
    portal = get_portal(request)
    try:
        session = optional_session(request, portal)
    except RedisError:  # error pages must render even when Redis is down
        session = None
    return portal.views.error(request, status, session)


# Service exceptions that are answered with a portal error page.
SERVICE_ERROR_STATUS = {
    NotFoundError: 404,
    ForbiddenError: 403,
    UnavailableError: 503,
    InvalidCsrfError: 400,
    LoginFailedError: 400,
    RedisError: 503,  # fail closed (02 §10)
    UnknownUserError: 400,
}


def _service_error_handler(status: int):
    """Handler für eine Service-Exception bauen, der mit einem festen Status antwortet.

    :param status: HTTP-Status
    :return: Exception-Handler
    """
    async def handler(request: Request, exc: Exception):
        return render_error(request, status)
    return handler


def register_error_handlers(app: FastAPI) -> None:
    """Handler für Service-Exceptions, ``HTTPException``, ungültige Eingaben (422) und unerwartete Fehler (500) eintragen.

    Alle Fehler erscheinen als Portal-Seite (HTML), nie als JSON. Header der ``HTTPException`` (z. B. ``Allow``) bleiben erhalten.

    ``LoginRequiredError`` führt zum Redirect auf ``/login``; Static-Dateien erhalten nur den Status ohne Seite.

    :param app: Anwendung
    """
    @app.exception_handler(LoginRequiredError)
    async def login_required(request: Request, exc: LoginRequiredError):
        return RedirectResponse(login_url(request.url.path), status_code=302)

    for error_type, status in SERVICE_ERROR_STATUS.items():
        app.add_exception_handler(error_type, _service_error_handler(status))

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        if is_static_path(request.url.path):
            return Response(status_code=exc.status_code, headers=exc.headers)
        response = render_error(request, exc.status_code)
        response.headers.update(exc.headers or {})  # z. B. Allow bei 405
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        if is_static_path(request.url.path):
            return Response(status_code=422)
        return render_error(request, 422)

    @app.exception_handler(Exception)
    async def server_error(request: Request, exc: Exception):
        logger.exception("unhandled request_id={}", getattr(request.state, "request_id", "-"))
        return render_error(request, 500)
