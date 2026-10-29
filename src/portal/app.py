"""Anwendungsfabrik des Portals (nur Verdrahtung).

``auth_mode: oidc`` meldet über den IdP an (Keycloak in dev, Shibboleth in prod) und hält die
Sessions in Redis (02 §4); ``auth_mode: dev`` ist die Auswahl der Testpersonen mit Sessions im
Speicher. Platzhalter: Die Registry liest Manifeste aus einem Ordner (keine SQLite-Registry, kein
Prober), und ``/apps/<slug>/`` zeigt eine Platzhalter-Seite statt Traefik-Routing.
"""

from __future__ import annotations

from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from redis import Redis

from .context import build_portal
from .core.config import Config, load_config
from .core.kit import STATIC_PREFIX
from .router import (
    auth_router,
    dev_login_router,
    dev_router,
    health_router,
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
) -> FastAPI:
    """FastAPI-Anwendung aus der Konfiguration bauen.

    Baut den :class:`~portal.context.Portal`-Kontext, hängt Static-Dateien, Middleware,
    Fehlerbehandlung und die Router ein. Je nach ``auth_mode`` kommt der OIDC-Router oder die
    Testpersonen-Auswahl dazu, bei ``env: dev`` zusätzlich die Platzhalter-Apps.

    :param config: Fertige Konfiguration oder Pfad zur YAML-Datei
    :param redis_client: Redis-Client, z. B. ``fakeredis`` in Tests; sonst aus ``redis_url``
    :param http_client: HTTP-Client für den IdP, z. B. mit ``MockTransport`` in Tests
    :return: Die konfigurierte Anwendung
    :rtype: FastAPI
    :raises ConfigError: Falls die Konfiguration ungültig ist
    """
    cfg = config if isinstance(config, Config) else load_config(Path(config))

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.portal = build_portal(cfg, redis_client=redis_client, http_client=http_client)
    app.mount(STATIC_PREFIX, StaticFiles(directory=cfg.kit_dist), name="static")

    register_middleware(app)
    register_error_handlers(app)

    app.include_router(page_router)
    app.include_router(auth_router)
    app.include_router(nav_router)
    app.include_router(health_router)
    app.include_router(oidc_router if cfg.auth_mode == "oidc" else dev_login_router)
    if cfg.dev:
        app.include_router(dev_router)
    return app
