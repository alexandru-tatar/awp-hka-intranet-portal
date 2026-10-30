"""Prüft jede Anfrage vor allen Routen (06 §4) und schreibt eine Logzeile (06 §11)."""

from __future__ import annotations

import json
import logging
import sys
import time
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from . import devshim, pages
from .context import User, current_assertion, current_request_id, current_user
from .errors import VerifyError
from .verify import verify

if TYPE_CHECKING:
    from .portal import Portal

ASSERTION_HEADER = "x-portal-assertion"
log = logging.getLogger("platform_sdk.access")
if not log.handlers:  # JSON-Zeilen auf stdout, unabhängig von der Log-Einstellung von uvicorn
    log.addHandler(logging.StreamHandler(sys.stdout))
    log.setLevel(logging.INFO)
    log.propagate = False


class PortalMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, portal: Portal) -> None:
        super().__init__(app)
        self.portal = portal

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = time.perf_counter()
        current_request_id.set(request.headers.get("x-request-id"))
        path = request.url.path
        if path == "/healthz" and request.method in ("GET", "HEAD"):
            return await call_next(request)
        cfg = self.portal.config
        if cfg.dev and path.startswith("/__dev/"):
            return await call_next(request)

        token = request.headers.get(ASSERTION_HEADER)
        if cfg.dev and token is None:
            user = devshim.user_from_cookie(request)
            if user is None:
                return RedirectResponse("/__dev/login", status_code=303)
        else:
            if token is None:
                return self._finish(request, pages.error(request, 401, "Anmeldung fehlt", _LOGIN_HINT), started)
            try:
                claims = await verify(token, keys=self.portal.jwks, issuer=cfg.issuer, audience=cfg.slug)
            except VerifyError:
                return self._finish(request, pages.error(request, 401, "Anmeldung ungültig", _LOGIN_HINT), started)
            user = User(
                sub=claims["sub"],
                name=str(claims.get("name") or ""),
                roles=tuple(claims["roles"]),
                email=claims.get("email"),
            )
            current_assertion.set(token)

        current_user.set(user)
        request.state.portal_user = user
        return self._finish(request, await call_next(request), started, user)

    @staticmethod
    def _finish(request: Request, response: Response, started: float, user: User | None = None) -> Response:
        log.info(
            json.dumps(
                {
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "level": "info",
                    "event": "request",
                    "request_id": current_request_id.get(),
                    "user_hash": user.hash if user else None,
                    "path": request.url.path,
                    "status": response.status_code,
                    "ms": round((time.perf_counter() - started) * 1000),
                }
            )
        )
        return response


_LOGIN_HINT = "Bitte öffnen Sie die Anwendung über das Portal und melden Sie sich dort an."
