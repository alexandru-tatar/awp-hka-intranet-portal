"""Portal-Kontext: alles, was ein Handler braucht, einmal pro Anwendung aus der Konfiguration gebaut."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import httpx

from .auth.dev_users import DevUser, load_dev_users
from .auth.grants import GrantStore
from .auth.sessions import MemorySessionStore, SessionStore
from .core.config import Config
from .core.i18n import Messages
from .core.kit import Kit
from .registry import ManifestDirectorySource, ManifestValidator, Prober, Registry, StatusWriter
from .registry.registration import Registrar
from .service import AdminService, AppService, SessionService, SessionWriteService
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
    :ivar admin_service: Service der Verwaltungsseite für platform-admin
    :ivar session_service: Lesender Service für Sessions
    :ivar session_write_service: Schreibender Service für Sessions
    :ivar session_store: Session-Store im Speicher, nur bei ``auth_mode: dev``
    :ivar views: Rendert Seiten aus Templates
    :ivar dev_users: Testpersonen, leer bei ``auth_mode: gateway``
    :ivar prober: Prüft ``/healthz`` der Apps und setzt den Status, ``None`` ohne ``registry.probe``
    """
    cfg: Config
    kit: Kit
    t: Messages
    registry: Registry
    app_service: AppService
    admin_service: AdminService
    session_service: SessionService | None
    session_write_service: SessionWriteService | None
    session_store: SessionStore | None
    views: Views
    dev_users: Mapping[str, DevUser]
    prober: Prober | None = None


def build_portal(
    cfg: Config,
    *,
    http_client: httpx.Client | None = None,
    app_transport: httpx.AsyncBaseTransport | None = None,
) -> Portal:
    """Den Kontext aus der Konfiguration bauen.

    Bei ``auth_mode: dev`` gibt es einen Session-Store im Speicher, bei ``auth_mode: gateway`` keine
    eigenen Sessions: die Identität kommt vom separaten Security-Gateway.

    :param cfg: Konfiguration
    :param http_client: nicht mehr verwendet, bleibt für bestehende Aufrufer
    :param app_transport: Transport zu den App-Containern statt des Netzwerks (Prober), für Tests
    :return: Der fertige Kontext
    :rtype: Portal
    """
    kit = Kit.load(cfg.kit_dist)
    t = Messages(MESSAGES_FILE, defaults={"kontakt": cfg.kontakt})
    registry = _build_registry(cfg)
    registry.reload()
    sessions: SessionStore | None = MemorySessionStore() if cfg.auth_mode == "dev" else None
    dev_users = load_dev_users(cfg.dev_users_file) if cfg.auth_mode == "dev" else {}
    app_service = AppService(registry)
    grants = GrantStore(cfg.grants_file) if cfg.grants_file is not None else None
    registrar = (
        Registrar(cfg.manifests_dir, cfg.registry.owners_file,
                  ManifestValidator(cfg.schema_path, cfg.role_vocabulary, cfg.adapter_scopes), cfg.role_vocabulary)
        if cfg.registry.owners_file is not None else None
    )
    admin_service = AdminService(registry, registrar, grants, cfg.role_vocabulary, writable=cfg.registry.admin_write)
    session_write_service = SessionWriteService(sessions, dev_users) if sessions is not None else None
    return Portal(
        cfg=cfg,
        kit=kit,
        t=t,
        registry=registry,
        app_service=app_service,
        admin_service=admin_service,
        session_service=SessionService(sessions) if sessions is not None else None,
        session_write_service=session_write_service,
        session_store=sessions,
        views=Views(TEMPLATES_DIR, apps=app_service, t=t, kit=kit, cfg=cfg),
        dev_users=dev_users,
        prober=(
            Prober(registry, cfg.apps, app_transport,
                   status_writer=StatusWriter(cfg.registry.status_file) if cfg.registry.status_file else None)
            if cfg.registry.probe and cfg.apps is not None else None
        ),
    )


def _build_registry(cfg: Config) -> Registry:
    """Registry mit Manifest-Ordner als Quelle bauen.

    Mit ``registry.probe`` setzt der Prober den Status, die Registry behält ihn dann beim Neuladen.

    :param cfg: Konfiguration
    :return: Noch nicht geladene Registry
    :rtype: Registry
    """
    validator = ManifestValidator(cfg.schema_path, cfg.role_vocabulary, cfg.adapter_scopes)
    source = ManifestDirectorySource(cfg.manifests_dir, validator, cfg.state_file, probe=cfg.registry.probe)
    return Registry(source, keep_status=cfg.registry.probe)
