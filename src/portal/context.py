"""Portal-Kontext: alles, was ein Handler braucht, einmal pro Anwendung aus der Konfiguration gebaut."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import httpx
from redis import Redis

from .auth.dev_users import DevUser, load_dev_users
from .auth.oidc import OidcClient
from .auth.redis_sessions import RedisLoginStore, RedisSessionStore
from .auth.roles import load_role_mapper
from .auth.sessions import MemorySessionStore, SessionStore
from .core.config import Config
from .core.i18n import Messages
from .core.kit import Kit
from .registry import ManifestDirectorySource, ManifestValidator, Registry
from .service import AppService, LoginService, SessionService, SessionWriteService
from .web.views import Views

PACKAGE_DIR = Path(__file__).resolve().parent
MESSAGES_FILE = PACKAGE_DIR / "locales" / "messages.de.yml"
TEMPLATES_DIR = PACKAGE_DIR / "templates"


@dataclass(frozen=True)
class Portal:
    """Unveränderlicher Kontext der Anwendung, erreichbar über ``request.app.state.portal``.

    :ivar cfg: Konfiguration
    :ivar kit: Asset-URLs des Design-Kits
    :ivar t: UI-Texte
    :ivar registry: Registry mit dem aktuellen Snapshot der Apps
    :ivar app_service: Service für Apps
    :ivar session_service: Lesender Service für Sessions
    :ivar session_write_service: Schreibender Service für Sessions
    :ivar login_service: Service für die OIDC-Anmeldung, ``None`` bei ``auth_mode: dev``
    :ivar session_store: Session-Store (Redis oder Speicher), für ``/readyz``
    :ivar views: Rendert Seiten aus Templates
    :ivar dev_users: Testpersonen, leer bei ``auth_mode: oidc``
    """
    cfg: Config
    kit: Kit
    t: Messages
    registry: Registry
    app_service: AppService
    session_service: SessionService
    session_write_service: SessionWriteService
    login_service: LoginService | None
    session_store: SessionStore
    views: Views
    dev_users: Mapping[str, DevUser]


def build_portal(
    cfg: Config, *, redis_client: Redis | None = None, http_client: httpx.Client | None = None
) -> Portal:
    """Den Kontext aus der Konfiguration bauen.

    Wählt den Session-Store (Redis, wenn ``redis_url`` gesetzt ist oder ein Client übergeben wird,
    sonst Speicher), lädt die Registry und baut bei ``auth_mode: oidc`` den Login-Service.

    :param cfg: Konfiguration
    :param redis_client: Redis-Client, sonst aus ``cfg.redis_url``
    :param http_client: HTTP-Client für den IdP, sonst ein Standardclient
    :return: Der fertige Kontext
    :rtype: Portal
    """
    kit = Kit.load(cfg.kit_dist)
    t = Messages(MESSAGES_FILE, defaults={"kontakt": cfg.kontakt})
    registry = _build_registry(cfg)
    registry.reload()
    client = redis_client or (Redis.from_url(cfg.redis_url, decode_responses=True) if cfg.redis_url else None)
    sessions: SessionStore = (
        RedisSessionStore(
            client,
            idle_seconds=cfg.idle_seconds,
            absolute_seconds=cfg.absolute_seconds,
            touch_min_interval_seconds=cfg.touch_min_interval_seconds,
        )
        if client is not None
        else MemorySessionStore()
    )
    dev_users = load_dev_users(cfg.dev_users_file) if cfg.auth_mode == "dev" else {}
    app_service = AppService(registry)
    session_write_service = SessionWriteService(sessions, dev_users)
    login_service = None
    if cfg.oidc is not None:
        assert client is not None and cfg.roles_file is not None  # checked by load_config
        login_service = LoginService(
            OidcClient(cfg.oidc, http_client),
            RedisLoginStore(client, ttl_seconds=cfg.login_state_ttl_seconds),
            load_role_mapper(cfg.roles_file, cfg.grants_file),
            session_write_service,
        )
    return Portal(
        cfg=cfg,
        kit=kit,
        t=t,
        registry=registry,
        app_service=app_service,
        session_service=SessionService(sessions),
        session_write_service=session_write_service,
        login_service=login_service,
        session_store=sessions,
        views=Views(TEMPLATES_DIR, apps=app_service, t=t, kit=kit, cfg=cfg),
        dev_users=dev_users,
    )


def _build_registry(cfg: Config) -> Registry:
    """Registry mit Manifest-Ordner als Quelle bauen.

    :param cfg: Konfiguration
    :return: Noch nicht geladene Registry
    :rtype: Registry
    """
    validator = ManifestValidator(cfg.schema_path, cfg.role_vocabulary, cfg.adapter_scopes)
    return Registry(ManifestDirectorySource(cfg.manifests_dir, validator, cfg.state_file))
