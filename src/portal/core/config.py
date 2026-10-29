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
class OidcConfig:
    """Einstellungen des OIDC-Clients (Abschnitt ``oidc``).

    :ivar issuer: Issuer des IdP, muss exakt dem ``iss`` im ID-Token entsprechen
    :ivar client_id: Client-ID des Portals
    :ivar client_secret: Client-Secret, aus ``client_secret_file`` gelesen
    :ivar redirect_uri: Adresse des Callbacks ``/oidc/callback``
    :ivar post_logout_redirect_uri: Adresse, zu der der IdP nach der Abmeldung zurückleitet; ohne Wert wird nur die Portal-Session beendet
    :ivar discovery_url: Adresse der Discovery, falls abweichend von ``<issuer>/.well-known/openid-configuration``
    :ivar scopes: Angeforderte Scopes
    :ivar id_token_algs: Erlaubte Signaturalgorithmen des ID-Tokens
    :ivar clock_leeway_seconds: Toleranz für ``exp`` und ``iat`` in Sekunden
    """
    issuer: str
    client_id: str
    client_secret: str
    redirect_uri: str
    post_logout_redirect_uri: str | None = None
    discovery_url: str | None = None
    scopes: tuple[str, ...] = ("openid", "profile", "email")
    id_token_algs: tuple[str, ...] = ("RS256", "ES256")
    clock_leeway_seconds: int = 60


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
    :ivar login_cookie: Name des Cookies, das den Browser an die Login-Transaktion bindet
    :ivar cookie_secure: Cookies nur über HTTPS senden
    :ivar auth_mode: ``dev`` (Testpersonen) oder ``oidc``
    :ivar redis_url: Adresse von Redis; ohne sie liegen die Sessions im Speicher
    :ivar idle_seconds: Inaktivitätsgrenze einer Session
    :ivar absolute_seconds: Maximale Lebensdauer einer Session
    :ivar touch_min_interval_seconds: Mindestabstand zwischen zwei Aktualisierungen von ``last_seen``
    :ivar login_state_ttl_seconds: Lebensdauer einer Login-Transaktion
    :ivar oidc: Einstellungen des OIDC-Clients, nur bei ``auth_mode: oidc``
    :ivar logging: Einstellungen des Loggings
    :ivar roles_file: Zuordnung IdP-Claims zu Rollen
    :ivar grants_file: Zusätzliche Rollen je Subject
    :ivar links: Footer-Links
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
    login_cookie: str = "portal_login"
    cookie_secure: bool = False
    auth_mode: str = "dev"
    redis_url: str | None = None
    idle_seconds: int = 1800
    absolute_seconds: int = 28800
    touch_min_interval_seconds: int = 60
    login_state_ttl_seconds: int = 600
    oidc: OidcConfig | None = None
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    roles_file: Path | None = None
    grants_file: Path | None = None
    links: Links = field(default_factory=Links)

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
    "login_cookie", "cookie_secure", "auth_mode", "redis_url", "idle_seconds", "absolute_seconds",
    "touch_min_interval_seconds", "login_state_ttl_seconds", "oidc", "logging", "roles_file", "grants_file",
}
_OIDC_KEYS = {
    "issuer", "client_id", "client_secret_file", "redirect_uri", "post_logout_redirect_uri", "discovery_url", "scopes",
    "id_token_algs", "clock_leeway_seconds",
}


def load_config(path: Path) -> Config:
    """Konfiguration aus einer YAML-Datei laden und prüfen.

    Relative Pfade gelten relativ zur Datei. ``auth_mode: dev`` ist nur mit ``env: dev`` erlaubt und
    braucht eine existierende ``dev_users_file``; ``auth_mode: oidc`` braucht ``redis_url``, einen
    ``oidc``-Abschnitt und ``roles_file``.

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
    if auth_mode not in ("dev", "oidc"):
        raise ConfigError(f"{path}: auth_mode must be dev or oidc")
    for key in ("kontakt", "manifests_dir", "schema_path", "kit_dist", "role_vocabulary"):
        if not raw.get(key):
            raise ConfigError(f"{path}: missing key {key}")

    links_raw = raw.get("links") or {}
    unknown_links = set(links_raw) - {"help", "privacy", "imprint"}
    if unknown_links:
        raise ConfigError(f"{path}: unknown links key(s) {', '.join(sorted(unknown_links))}")

    oidc = _load_oidc(path, base, raw.get("oidc")) if auth_mode == "oidc" else None

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
        login_cookie=raw.get("login_cookie", "portal_login"),
        cookie_secure=bool(raw.get("cookie_secure", False)),
        auth_mode=auth_mode,
        redis_url=raw.get("redis_url"),
        idle_seconds=int(raw.get("idle_seconds", 1800)),
        absolute_seconds=int(raw.get("absolute_seconds", 28800)),
        touch_min_interval_seconds=int(raw.get("touch_min_interval_seconds", 60)),
        login_state_ttl_seconds=int(raw.get("login_state_ttl_seconds", 600)),
        oidc=oidc,
        logging=_load_logging(path, base, raw.get("logging"), env),
        roles_file=p("roles_file"),
        grants_file=p("grants_file"),
        links=Links(**links_raw),
    )
    for key in ("manifests_dir", "schema_path", "kit_dist"):
        if not getattr(cfg, key).exists():
            raise ConfigError(f"{path}: {key} does not exist: {getattr(cfg, key)}")
    if cfg.auth_mode == "dev":
        if not cfg.dev:
            raise ConfigError(f"{path}: auth_mode dev is only allowed with env dev")
        if not (cfg.dev_users_file and cfg.dev_users_file.exists()):
            raise ConfigError(f"{path}: auth_mode dev needs an existing dev_users_file")
    else:
        if not cfg.redis_url:
            raise ConfigError(f"{path}: auth_mode oidc needs redis_url")
        if not (cfg.roles_file and cfg.roles_file.exists()):
            raise ConfigError(f"{path}: auth_mode oidc needs an existing roles_file")
        if cfg.grants_file and not cfg.grants_file.exists():
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


def _load_oidc(path: Path, base: Path, raw: dict | None) -> OidcConfig:
    """Den Abschnitt ``oidc`` lesen und prüfen.

    :param path: Pfad der Konfigurationsdatei, für Fehlermeldungen
    :param base: Ordner der Konfigurationsdatei, Basis für ``client_secret_file``
    :param raw: Rohwerte des Abschnitts
    :return: Die OIDC-Einstellungen mit gelesenem Client-Secret
    :rtype: OidcConfig
    :raises ConfigError: Falls der Abschnitt fehlt, unbekannte Schlüssel enthält oder Pflichtwerte fehlen
    """
    if not raw:
        raise ConfigError(f"{path}: auth_mode oidc needs an oidc section")
    unknown = set(raw) - _OIDC_KEYS
    if unknown:
        raise ConfigError(f"{path}: unknown oidc key(s) {', '.join(sorted(unknown))}")
    for key in ("issuer", "client_id", "client_secret_file", "redirect_uri"):
        if not raw.get(key):
            raise ConfigError(f"{path}: missing oidc key {key}")
    secret_file = (base / raw["client_secret_file"]).resolve()
    if not secret_file.exists():
        raise ConfigError(f"{path}: oidc client_secret_file does not exist: {secret_file}")
    optional = {k: raw[k] for k in ("post_logout_redirect_uri", "discovery_url", "scopes", "id_token_algs", "clock_leeway_seconds") if k in raw}
    for key in ("scopes", "id_token_algs"):
        if key in optional:
            optional[key] = tuple(optional[key])
    return OidcConfig(
        issuer=raw["issuer"].rstrip("/"),
        client_id=raw["client_id"],
        client_secret=secret_file.read_text(encoding="utf-8").strip(),
        redirect_uri=raw["redirect_uri"],
        **optional,
    )
