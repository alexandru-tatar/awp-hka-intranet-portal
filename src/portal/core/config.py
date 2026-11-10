"""Konfiguration des Portals (Teilmenge von gateway.yml, 02 §2).

Unbekannte Schlüssel sind ein Fehler, wie beim Manifest-Schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import yaml


class ConfigError(Exception):
    """Die Konfigurationsdatei ist ungültig oder unvollständig."""
    pass


@dataclass(frozen=True)
class Links:
    """Links im Footer.

    :ivar help: Hilfe
    :ivar privacy: Datenschutz
    :ivar imprint: Impressum
    """
    help: str = "#"
    privacy: str = "#"
    imprint: str = "#"


@dataclass(frozen=True)
class LoggingConfig:
    """Einstellungen des Loggings (Abschnitt ``logging``).

    :ivar console_level: Mindestlevel der Konsole (``TRACE`` bis ``CRITICAL``)
    :ivar color: Farben in der Konsole: ``auto`` (nur auf einem Terminal), ``always`` oder ``never``
    :ivar file: Pfad der Logdatei; ohne Wert wird nur auf die Konsole geschrieben
    :ivar file_level: Mindestlevel der Logdatei
    :ivar rotation: Wann eine neue Logdatei beginnt, z. B. ``10 MB``
    :ivar retention: Anzahl aufbewahrter, rotierter Logdateien
    :ivar levels: Mindestlevel je Logger (Modulname und alles darunter), überschreibt die Mindestlevel oben
    """

    console_level: str = "INFO"
    color: str = "auto"
    file: Path | None = None
    file_level: str = "INFO"
    rotation: str = "10 MB"
    retention: int = 3
    levels: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class AppsConfig:
    """Weiterleitung an die App-Container (Abschnitt ``apps``).

    :ivar upstream: Adresse eines App-Containers mit ``{slug}`` als Platzhalter, z. B. ``http://app-{slug}:8080``
    :ivar connect_timeout_seconds: Zeitlimit für den Verbindungsaufbau
    :ivar read_timeout_seconds: Zeitlimit für die Antwort der App
    :ivar max_body_bytes: Größte erlaubte Anfrage an eine App
    """
    upstream: str
    connect_timeout_seconds: float = 2.0
    read_timeout_seconds: float = 30.0
    max_body_bytes: int = 10 * 1024 * 1024

    def upstream_for(self, slug: str) -> str:
        """Adresse des Containers einer App.

        :param slug: Slug der App
        :return: Basisadresse ohne abschließenden Slash
        :rtype: str
        """
        return self.upstream.replace("{slug}", slug).rstrip("/")


@dataclass(frozen=True)
class RegistryConfig:
    """Einstellungen der Registry (Abschnitt ``registry``).

    :ivar refresh_seconds: Abstand, in dem das Portal den Manifest-Ordner auf Änderungen prüft
    :ivar probe: ``True``, wenn das Portal ``/healthz`` jeder App prüft und den Status selbst setzt
    :ivar owners_file: JSON-Datei ``{slug: owner}``, die nur der Befehl ``python -m portal.registry`` schreibt
    :ivar status_file: JSON-Datei, in die der Prober den Status schreibt und die ``list`` liest (HKA-56)
    :ivar admin_write: ``True``, wenn die Verwaltungsseite Apps entfernen, Rollen ändern und Grants schreiben darf.
        Braucht ``owners_file`` und beschreibbare Ordner für Manifeste und Grants; sonst zeigt die Seite nur an.
    """
    refresh_seconds: float = 5.0
    probe: bool = False
    owners_file: Path | None = None
    status_file: Path | None = None
    admin_write: bool = False


@dataclass(frozen=True)
class GatewayConfig:
    issuer: str
    jwks_url: str
    public_url: str
    audience: str = "hka-portal-ui"


@dataclass(frozen=True)
class Config:
    """Geprüfte Konfiguration des Portals.

    :ivar env: ``dev`` oder ``prod``
    :ivar kontakt: Kontaktangabe für Fehlerseiten
    :ivar manifests_dir: Ordner mit den App-Manifesten
    :ivar schema_path: JSON-Schema der Manifeste
    :ivar kit_dist: Ordner mit dem gebauten Design-Kit
    :ivar role_vocabulary: Rollen, die Manifeste verwenden dürfen
    :ivar adapter_scopes: Adapter-Scopes, die Manifeste verwenden dürfen
    :ivar state_file: Status je App (Platzhalter für den Prober)
    :ivar dev_users_file: Testpersonen (nur ``auth_mode: dev``)
    :ivar session_cookie: Name des Session-Cookies
    :ivar cookie_secure: Cookies nur über HTTPS senden
    :ivar auth_mode: ``dev`` (Testpersonen, Sessions im Speicher) oder ``gateway`` (Identität vom separaten Security-Gateway)
    :ivar logging: Einstellungen des Loggings
    :ivar grants_file: Zusätzliche Rollen je Subject
    :ivar links: Footer-Links
    :ivar apps: Adressen der App-Container für den Prober, ``None`` ohne Abschnitt
    :ivar registry: Nachladen der Manifeste, Prober und Besitzerdatei
    """
    env: str
    kontakt: str
    manifests_dir: Path
    schema_path: Path
    kit_dist: Path
    role_vocabulary: tuple[str, ...]
    adapter_scopes: tuple[str, ...]
    state_file: Path | None = None
    dev_users_file: Path | None = None
    session_cookie: str = "portal_sid"
    cookie_secure: bool = False
    auth_mode: str = "dev"
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    grants_file: Path | None = None
    links: Links = field(default_factory=Links)
    apps: AppsConfig | None = None
    registry: RegistryConfig = field(default_factory=RegistryConfig)
    gateway: GatewayConfig | None = None

    @property
    def dev(self) -> bool:
        """Ob die Umgebung ``dev`` ist.

        :return: ``True`` bei ``env: dev``
        :rtype: bool
        """
        return self.env == "dev"


_KEYS = {
    "env", "kontakt", "manifests_dir", "schema_path", "kit_dist", "role_vocabulary",
    "adapter_scopes", "state_file", "dev_users_file", "session_cookie", "links",
    "cookie_secure", "auth_mode", "logging", "grants_file",
    "apps", "registry", "gateway",
}
_REGISTRY_KEYS = {"refresh_seconds", "probe", "owners_file", "status_file", "admin_write"}
_APPS_KEYS = {"upstream", "connect_timeout_seconds", "read_timeout_seconds", "max_body_bytes"}


def load_config(path: Path) -> Config:
    """Konfiguration aus einer YAML-Datei laden und prüfen.

    Relative Pfade gelten relativ zur Datei. ``auth_mode: dev`` ist nur mit ``env: dev`` erlaubt und
    braucht eine existierende ``dev_users_file``; ``auth_mode: gateway`` braucht den Abschnitt ``gateway``.

    :param path: Pfad zur YAML-Datei
    :return: Die geprüfte Konfiguration
    :rtype: Config
    :raises ConfigError: Bei unbekannten oder fehlenden Schlüsseln, ungültigen Werten oder fehlenden Dateien
    """
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    unknown = set(raw) - _KEYS
    if unknown:
        raise ConfigError(f"{path}: unknown key(s) {', '.join(sorted(unknown))}")
    base = path.parent

    def p(key: str) -> Path | None:
        return (base / raw[key]).resolve() if raw.get(key) else None

    env = raw.get("env", "prod")
    if env not in ("dev", "prod"):
        raise ConfigError(f"{path}: env must be dev or prod")
    auth_mode = raw.get("auth_mode", "dev")
    if auth_mode not in ("dev", "gateway"):
        raise ConfigError(f"{path}: auth_mode must be dev or gateway")
    for key in ("kontakt", "manifests_dir", "schema_path", "kit_dist", "role_vocabulary"):
        if not raw.get(key):
            raise ConfigError(f"{path}: missing key {key}")

    links_raw = raw.get("links") or {}
    unknown_links = set(links_raw) - {"help", "privacy", "imprint"}
    if unknown_links:
        raise ConfigError(f"{path}: unknown links key(s) {', '.join(sorted(unknown_links))}")

    cfg = Config(
        env=env,
        kontakt=raw["kontakt"],
        manifests_dir=p("manifests_dir"),
        schema_path=p("schema_path"),
        kit_dist=p("kit_dist"),
        role_vocabulary=tuple(raw["role_vocabulary"]),
        adapter_scopes=tuple(raw.get("adapter_scopes") or ()),
        state_file=p("state_file"),
        dev_users_file=p("dev_users_file"),
        session_cookie=raw.get("session_cookie", "portal_sid"),
        cookie_secure=bool(raw.get("cookie_secure", False)),
        auth_mode=auth_mode,
        logging=_load_logging(path, base, raw.get("logging"), env),
        grants_file=p("grants_file"),
        links=Links(**links_raw),
        apps=_load_apps(path, raw.get("apps")),
        registry=_load_registry(path, base, raw.get("registry")),
        gateway=GatewayConfig(**raw["gateway"]) if raw.get("gateway") else None,
    )
    if cfg.registry.probe:
        if cfg.apps is None:
            raise ConfigError(f"{path}: registry probe needs an apps section")
        if cfg.state_file is not None:
            raise ConfigError(f"{path}: registry probe sets the status itself, remove state_file")
    for key in ("manifests_dir", "schema_path", "kit_dist"):
        if not getattr(cfg, key).exists():
            raise ConfigError(f"{path}: {key} does not exist: {getattr(cfg, key)}")
    if cfg.auth_mode == "dev":
        if not cfg.dev:
            raise ConfigError(f"{path}: auth_mode dev is only allowed with env dev")
        if not (cfg.dev_users_file and cfg.dev_users_file.exists()):
            raise ConfigError(f"{path}: auth_mode dev needs an existing dev_users_file")
    elif cfg.auth_mode == "gateway":
        if cfg.gateway is None:
            raise ConfigError("auth_mode gateway requires gateway settings")
        from urllib.parse import urlsplit
        for value in (cfg.gateway.issuer, cfg.gateway.jwks_url, cfg.gateway.public_url):
            parts = urlsplit(value)
            if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
                raise ConfigError("Invalid gateway URL")
        if cfg.gateway.audience in ("portal", "adapters") or not cfg.gateway.audience:
            raise ConfigError("Dedicated portal audience required")
    if cfg.grants_file and not cfg.grants_file.exists():
        # Mit admin_write legt die Verwaltungsseite die Datei bei der ersten Änderung an; dann genügt der Ordner.
        if not (cfg.registry.admin_write and cfg.grants_file.parent.is_dir()):
            raise ConfigError(f"{path}: grants_file does not exist: {cfg.grants_file}")
    return cfg


_LOG_LEVELS = ("TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL")
_LOGGING_KEYS = {"console_level", "color", "file", "file_level", "rotation", "retention", "levels"}


def _load_logging(path: Path, base: Path, raw: dict | None, env: str) -> LoggingConfig:
    """Den Abschnitt ``logging`` lesen und prüfen.

    Ohne Angabe ist die Konsole in dev auf ``DEBUG`` und in prod auf ``INFO`` gestellt.

    :param path: Pfad der Konfigurationsdatei, für Fehlermeldungen
    :param base: Ordner der Konfigurationsdatei, Basis für einen relativen ``file``
    :param raw: Rohwerte des Abschnitts, ``None`` ohne Abschnitt
    :param env: ``dev`` oder ``prod``
    :return: Die Logging-Einstellungen
    :rtype: LoggingConfig
    :raises ConfigError: Bei unbekannten Schlüsseln oder unbekannten Leveln
    """
    raw = raw or {}
    unknown = set(raw) - _LOGGING_KEYS
    if unknown:
        raise ConfigError(f"{path}: unknown logging key(s) {', '.join(sorted(unknown))}")
    default_level = "DEBUG" if env == "dev" else "INFO"
    levels = {str(k): str(v).upper() for k, v in (raw.get("levels") or {}).items()}
    console = str(raw.get("console_level", default_level)).upper()
    file_level = str(raw.get("file_level", default_level)).upper()
    color = str(raw.get("color", "auto")).lower()
    if color not in ("auto", "always", "never"):
        raise ConfigError(f"{path}: logging color must be auto, always or never")
    for level in (console, file_level, *levels.values()):
        if level not in _LOG_LEVELS:
            raise ConfigError(f"{path}: unknown log level '{level}'")
    return LoggingConfig(
        console_level=console,
        color=color,
        file=(base / raw["file"]).resolve() if raw.get("file") else None,
        file_level=file_level,
        rotation=str(raw.get("rotation", "10 MB")),
        retention=int(raw.get("retention", 3)),
        levels=levels,
    )


def _load_apps(path: Path, raw: dict | None) -> AppsConfig | None:
    """Den Abschnitt ``apps`` lesen und prüfen.

    :param path: Pfad der Konfigurationsdatei, für Fehlermeldungen
    :param raw: Rohwerte des Abschnitts, ``None`` ohne Abschnitt
    :return: Die Einstellungen oder ``None``
    :rtype: AppsConfig | None
    :raises ConfigError: Bei unbekannten Schlüsseln, fehlendem ``upstream`` oder ungültigen Grenzen
    """
    if raw is None:
        return None
    unknown = set(raw) - _APPS_KEYS
    if unknown:
        raise ConfigError(f"{path}: unknown apps key(s) {', '.join(sorted(unknown))}")
    upstream = str(raw.get("upstream") or "")
    if not upstream.startswith(("http://", "https://")):
        raise ConfigError(f"{path}: apps upstream must start with http:// or https://")
    cfg = AppsConfig(
        upstream=upstream,
        connect_timeout_seconds=float(raw.get("connect_timeout_seconds", 2)),
        read_timeout_seconds=float(raw.get("read_timeout_seconds", 30)),
        max_body_bytes=int(raw.get("max_body_bytes", 10 * 1024 * 1024)),
    )
    if min(cfg.connect_timeout_seconds, cfg.read_timeout_seconds, cfg.max_body_bytes) <= 0:
        raise ConfigError(f"{path}: apps timeouts and max_body_bytes must be positive")
    return cfg


def _load_registry(path: Path, base: Path, raw: dict | None) -> RegistryConfig:
    """Den Abschnitt ``registry`` lesen und prüfen.

    :param path: Pfad der Konfigurationsdatei, für Fehlermeldungen
    :param base: Ordner der Konfigurationsdatei, Basis für relative ``owners_file`` und ``status_file``
    :param raw: Rohwerte des Abschnitts, ``None`` ohne Abschnitt
    :return: Die Einstellungen, ohne Abschnitt die Voreinstellung
    :rtype: RegistryConfig
    :raises ConfigError: Bei unbekannten Schlüsseln, falschen Typen oder einem Abstand unter einer Sekunde
    """
    if raw is None:
        return RegistryConfig()
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: registry must be a mapping")
    unknown = set(raw) - _REGISTRY_KEYS
    if unknown:
        raise ConfigError(f"{path}: unknown registry key(s) {', '.join(sorted(unknown))}")
    if not isinstance(raw.get("probe", False), bool):
        raise ConfigError(f"{path}: registry probe must be true or false")
    if not isinstance(raw.get("admin_write", False), bool):
        raise ConfigError(f"{path}: registry admin_write must be true or false")
    if raw.get("admin_write") and not raw.get("owners_file"):
        raise ConfigError(f"{path}: registry admin_write needs owners_file")
    refresh = float(raw.get("refresh_seconds", 5))
    if refresh < 1:
        raise ConfigError(f"{path}: registry refresh_seconds must be at least 1")
    return RegistryConfig(
        refresh_seconds=refresh,
        probe=raw.get("probe", False),
        owners_file=(base / raw["owners_file"]).resolve() if raw.get("owners_file") else None,
        status_file=(base / raw["status_file"]).resolve() if raw.get("status_file") else None,
        admin_write=bool(raw.get("admin_write", False)),
    )
