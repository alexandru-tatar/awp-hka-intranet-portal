"""Anwendungsfabrik des Portals (nur Verdrahtung).

``auth_mode: oidc`` meldet über den IdP an (Keycloak in dev, Shibboleth in prod) und hält die
Sessions in Redis (02 §4); ``auth_mode: dev`` ist die Auswahl der Testpersonen mit Sessions im
Speicher. Die Registry liest Manifeste aus einem Ordner (keine SQLite-Registry) und lädt sie im Hintergrund neu.
Mit ``registry.probe`` prüft der Prober ``/healthz`` jeder App und setzt den Status. ``/apps/<slug>/`` wird mit
Abschnitt ``apps`` an den App-Container weitergeleitet, sonst zeigt es in dev eine Platzhalter-Seite.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from redis import Redis

from .context import build_portal
from .core.config import Config, load_config
from .core.kit import STATIC_PREFIX, KitStaticFiles
from .router import (
    app_router,
    auth_router,
    dev_login_router,
    dev_router,
    health_router,
    jwks_router,
    nav_router,
    oidc_router,
    page_router,
)
from .web.errors import register_error_handlers
from .web.middleware import register_middleware


def create_app(
    config: Config | Path | str,
    *,
    redis_client: Redis | None = None,
    http_client: httpx.Client | None = None,
    app_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    """FastAPI-Anwendung aus der Konfiguration bauen.

    Baut den :class:`~portal.context.Portal`-Kontext, hängt Static-Dateien, Middleware,
    Fehlerbehandlung und die Router ein. Je nach ``auth_mode`` kommt der OIDC-Router oder die
    Testpersonen-Auswahl dazu, bei ``env: dev`` zusätzlich die Platzhalter-Apps.

    :param config: Fertige Konfiguration oder Pfad zur YAML-Datei
    :param redis_client: Redis-Client, z. B. ``fakeredis`` in Tests; sonst aus ``redis_url``
    :param http_client: HTTP-Client für den IdP, z. B. mit ``MockTransport`` in Tests
    :param app_transport: Transport zu den App-Containern, z. B. ``MockTransport`` in Tests
    :return: Die konfigurierte Anwendung
    :rtype: FastAPI
    :raises ConfigError: Falls die Konfiguration ungültig ist
    """
    cfg = config if isinstance(config, Config) else load_config(Path(config))

    portal = build_portal(cfg, redis_client=redis_client, http_client=http_client, app_transport=app_transport)

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
        if portal.proxy is not None:
            await portal.proxy.aclose()

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.portal = portal
    app.mount(STATIC_PREFIX, KitStaticFiles(directory=cfg.kit_dist, kit=portal.kit), name="static")

    register_middleware(app)
    register_error_handlers(app)

    app.include_router(page_router)
    app.include_router(auth_router)
    app.include_router(nav_router)
    app.include_router(health_router)
    app.include_router(jwks_router)
    app.include_router(oidc_router if cfg.auth_mode == "oidc" else dev_login_router)
    if cfg.apps is not None:
        app.include_router(app_router)
    elif cfg.dev:
        app.include_router(dev_router)
    return app
