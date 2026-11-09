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
class AssertionConfig:
    """Einstellungen des Identitäts-Tokens für Apps (Abschnitt ``assertion``).

    :ivar issuer: Wert von ``iss``, muss dem ``PORTAL_ISSUER`` der Apps exakt entsprechen
    :ivar ttl_seconds: Gültigkeit eines Tokens in Sekunden
    :ivar signing_key_current: PEM-Datei des aktuellen Signaturschlüssels; ohne Wert erzeugt ``env: dev`` einen flüchtigen
    :ivar signing_key_next: PEM-Datei des nächsten Schlüssels, wird nur im JWKS veröffentlicht
    :ivar signing_key_previous: PEM-Datei des vorigen Schlüssels, wird nur im JWKS veröffentlicht
    """
    issuer: str
    ttl_seconds: int = 60
    signing_key_current: Path | None = None
    signing_key_next: Path | None = None
    signing_key_previous: Path | None = None


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
    :ivar assertion: Identitäts-Token für Apps, ``None`` ohne Abschnitt
    :ivar apps: Weiterleitung an App-Container, ``None`` ohne Abschnitt (dann Platzhalter bzw. 404)
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
    assertion: AssertionConfig | None = None
    apps: AppsConfig | None = None
    registry: RegistryConfig = field(default_factory=RegistryConfig)

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
    "assertion", "apps", "registry",
}
_REGISTRY_KEYS = {"refresh_seconds", "probe", "owners_file", "status_file", "admin_write"}
_ASSERTION_KEYS = {"issuer", "ttl_seconds", "signing_key_current", "signing_key_next", "signing_key_previous"}
_APPS_KEYS = {"upstream", "connect_timeout_seconds", "read_timeout_seconds", "max_body_bytes"}
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
        assertion=_load_assertion(path, base, raw.get("assertion")),
        apps=_load_apps(path, raw.get("apps")),
        registry=_load_registry(path, base, raw.get("registry")),
    )
    if cfg.registry.probe:
        if cfg.apps is None:
            raise ConfigError(f"{path}: registry probe needs an apps section")
        if cfg.state_file is not None:
            raise ConfigError(f"{path}: registry probe sets the status itself, remove state_file")
    if cfg.apps is not None:
        if cfg.assertion is None:
            raise ConfigError(f"{path}: apps needs an assertion section")
        if not cfg.dev and cfg.assertion.signing_key_current is None:
            raise ConfigError(f"{path}: apps in prod needs assertion.signing_key_current")
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


def _load_assertion(path: Path, base: Path, raw: dict | None) -> AssertionConfig | None:
    """Den Abschnitt ``assertion`` lesen und prüfen.

    :param path: Pfad der Konfigurationsdatei, für Fehlermeldungen
    :param base: Ordner der Konfigurationsdatei, Basis für die Schlüsseldateien
    :param raw: Rohwerte des Abschnitts, ``None`` ohne Abschnitt
    :return: Die Einstellungen oder ``None``
    :rtype: AssertionConfig | None
    :raises ConfigError: Bei unbekannten oder fehlenden Schlüsseln, ungültiger Laufzeit oder fehlenden Dateien
    """
    if raw is None:
        return None
    unknown = set(raw) - _ASSERTION_KEYS
    if unknown:
        raise ConfigError(f"{path}: unknown assertion key(s) {', '.join(sorted(unknown))}")
    if not raw.get("issuer"):
        raise ConfigError(f"{path}: missing assertion key issuer")
    ttl = int(raw.get("ttl_seconds", 60))
    if ttl < 1:
        raise ConfigError(f"{path}: assertion ttl_seconds must be positive")
    keys: dict[str, Path | None] = {}
    for key in ("signing_key_current", "signing_key_next", "signing_key_previous"):
        keys[key] = (base / raw[key]).resolve() if raw.get(key) else None
        if keys[key] is not None and not keys[key].exists():
            raise ConfigError(f"{path}: assertion {key} does not exist: {keys[key]}")
    return AssertionConfig(issuer=str(raw["issuer"]), ttl_seconds=ttl, **keys)


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
