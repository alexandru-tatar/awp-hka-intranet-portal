"""Anwendungsfabrik des Portals (nur Verdrahtung).

``auth_mode: gateway`` übernimmt die Identität aus der signierten Assertion des separaten Security-Gateways
(Login, Sessions, App-Routing und Token-Ausstellung liegen dort); ``auth_mode: dev`` ist die Auswahl der
Testpersonen mit Sessions im Speicher. Die Registry liest Manifeste aus einem Ordner und lädt sie im Hintergrund
neu. Mit ``registry.probe`` prüft der Prober ``/healthz`` jeder App und setzt den Status. In dev zeigt
``/apps/<slug>/`` eine Platzhalter-Seite.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI

from .auth.gateway import GatewayVerifier
from .context import build_portal
from .core.config import Config, load_config
from .core.kit import STATIC_PREFIX, KitStaticFiles
from .router import (
    admin_router,
    auth_router,
    dev_login_router,
    dev_router,
    health_router,
    nav_router,
    page_router,
)
from .router.internal_registry_router import create_registry_router
from .web.errors import register_error_handlers
from .web.middleware import register_middleware


def create_app(
    config: Config | Path | str,
    *,
    app_transport: httpx.AsyncBaseTransport | None = None,
    registry_token_file: Path | None = None,
    gateway_http_client: httpx.Client | None = None,
) -> FastAPI:
    """FastAPI-Anwendung aus der Konfiguration bauen.

    Baut den :class:`~portal.context.Portal`-Kontext, hängt Static-Dateien, Middleware,
    Fehlerbehandlung und die Router ein. Je nach ``auth_mode`` kommt der OIDC-Router oder die
    Testpersonen-Auswahl dazu, bei ``env: dev`` zusätzlich die Platzhalter-Apps.

    :param config: Fertige Konfiguration oder Pfad zur YAML-Datei
    :param app_transport: Transport zu den App-Containern, z. B. ``MockTransport`` in Tests
    :param registry_token_file: Optionale externe Secretdatei für die interne Registry-API
    :return: Die konfigurierte Anwendung
    :rtype: FastAPI
    :raises ConfigError: Falls die Konfiguration ungültig ist
    """
    cfg = config if isinstance(config, Config) else load_config(Path(config))

    portal = build_portal(cfg, app_transport=app_transport)

    verifier = GatewayVerifier(cfg.gateway, gateway_http_client) if cfg.auth_mode == "gateway" else None

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        tasks = [asyncio.create_task(portal.registry.watch(cfg.registry.refresh_seconds))]
        if portal.prober is not None:
            tasks.append(asyncio.create_task(portal.prober.run()))
        yield
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if portal.prober is not None:
            await portal.prober.aclose()
        if verifier is not None:
            verifier.close()

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.portal = portal
    app.state.gateway_verifier = verifier
    service_token_path = registry_token_file or os.environ.get("PORTAL_REGISTRY_SERVICE_TOKEN_FILE")
    if cfg.auth_mode == "gateway" and service_token_path is None:
        raise ValueError("Gateway mode requires PORTAL_REGISTRY_SERVICE_TOKEN_FILE")
    if service_token_path is not None:
        app.include_router(create_registry_router(portal.registry, Path(service_token_path), portal.app_service, verifier))
    app.mount(STATIC_PREFIX, KitStaticFiles(directory=cfg.kit_dist, kit=portal.kit), name="static")

    register_middleware(app)
    register_error_handlers(app)

    app.include_router(page_router)
    app.include_router(admin_router)
    if cfg.auth_mode != "gateway":
        app.include_router(auth_router)
    app.include_router(nav_router)
    app.include_router(health_router)
    if cfg.auth_mode != "gateway":
        app.include_router(dev_login_router)
    if cfg.auth_mode == "gateway":
        from fastapi.responses import JSONResponse
        from starlette.concurrency import run_in_threadpool
        import jwt

        @app.middleware("http")
        async def gateway_identity(request, call_next):
            path = request.url.path
            if path == "/readyz" or path == "/internal/apps" or path.startswith("/internal/"):
                return await call_next(request)
            values = request.headers.getlist("x-portal-assertion")
            navigation = path == "/nav" and request.headers.get("authorization", "").startswith("Bearer ")
            token = request.headers["authorization"][7:] if navigation else (values[0] if len(values) == 1 else None)
            try:
                request.state.gateway_user = await run_in_threadpool(verifier.verify, token, navigation=navigation)
            except (ValueError, TypeError, KeyError, jwt.PyJWTError, httpx.HTTPError):
                return JSONResponse({"detail": "Valid gateway assertion required"}, status_code=401, headers={"Cache-Control": "no-store"})
            if request.method not in ("GET", "HEAD", "OPTIONS") and (
                    request.headers.get("origin") != cfg.gateway.public_url or
                    request.headers.get("sec-fetch-site") in ("cross-site", "same-site")):
                return JSONResponse({"detail": "Foreign origin"}, status_code=403)
            # Kein App-Proxy und kein eigener Login in diesem Modus.
            if path == "/apps" or path.startswith("/apps/") or path in ("/login", "/logout"):
                return JSONResponse({"detail": "Use the security gateway"}, status_code=404)
            return await call_next(request)
    elif cfg.dev:
        app.include_router(dev_router)
    return app
