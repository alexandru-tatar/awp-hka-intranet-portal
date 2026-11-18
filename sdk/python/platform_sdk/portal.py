"""Öffentliche Schnittstelle des SDK (06 §3.1)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import devshim, pages
from .adapters import Adapters
from .adapters.bwsync import connect as bwsync_connect
from .config import Config
from .context import User
from .errors import AdapterError, PortalHTTPError
from .jwks import JwksCache
from .layout import Layout
from .middleware import PortalMiddleware

KIT_DIR = Path(__file__).parent / "kit"


class Portal:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.base_path = config.base_path
        self.manifest = config.manifest
        self.jwks = JwksCache(f"{config.api_url}/.well-known/jwks.json")
        self.adapters = Adapters(config)
        self._layout = Layout(config)

    @classmethod
    def from_env(cls, manifest_path: str = "manifest.json") -> Portal:
        return cls(Config.from_env(manifest_path))

    def install(self, app: FastAPI) -> None:
        """Prüfung der Anmeldung vor allen Routen, /healthz, im Entwicklungsmodus die Test-Anmeldung und die
        Standardbehandlung aller Fehler, die die App nicht selbst abfängt (sdk/README.md, „Fehler: Standard“)."""
        app.add_middleware(PortalMiddleware, portal=self)
        app.add_exception_handler(PortalHTTPError, self._error_response)
        app.add_exception_handler(AdapterError, self._unhandled)
        app.add_exception_handler(Exception, self._unhandled)

        @app.get("/healthz", include_in_schema=False)
        async def healthz() -> JSONResponse:
            return JSONResponse({"status": "ok"})

        @app.get(self.url(bwsync_connect.SCRIPT), include_in_schema=False)
        async def bwsync_connect_js() -> FileResponse:
            # Browser-Skript des SDK (ohne Oberfläche); nur für angemeldete Personen, wie jede Seite der App
            return FileResponse(bwsync_connect.SCRIPT_FILE, media_type="text/javascript; charset=utf-8",
                                headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-cache"})

        if self.config.dev:
            # kit/ legt erst `make sdk-release` an; in den SDK-Tests fehlt es
            app.mount("/__dev/kit", StaticFiles(directory=KIT_DIR, check_dir=False), name="portal-dev-kit")
            app.include_router(devshim.router(self))

    def router(self, **kw) -> APIRouter:
        return APIRouter(prefix=self.base_path, **kw)

    def user(self, request: Request) -> User:
        user = getattr(request.state, "portal_user", None)
        if user is None:
            raise PortalHTTPError(401, "Anmeldung fehlt", "Bitte melden Sie sich im Portal an.")
        return user

    def requires(self, *roles: str) -> Callable[[Request], Awaitable[User]]:
        async def dependency(request: Request) -> User:
            user = self.user(request)
            if not set(user.roles) & set(roles):
                raise PortalHTTPError(403, "Kein Zugriff", "Diese Seite ist für Ihre Rolle nicht freigegeben.")
            return user

        return dependency

    def url(self, path: str) -> str:
        if not path.startswith("/"):
            raise ValueError("portal.url() erwartet einen Pfad, der mit „/“ beginnt.")
        return self.base_path + path

    async def layout(self, *, title: str, body: str, current: str, user: User) -> str:
        return await self._layout.render(title=title, body=body, current=current, user=user)

    async def _error_response(self, request: Request, exc: Exception) -> Response:
        assert isinstance(exc, PortalHTTPError)
        return pages.error(request, exc.status, exc.title, exc.detail)

    async def _unhandled(self, request: Request, exc: Exception) -> Response:
        return pages.fallback(request, exc)
