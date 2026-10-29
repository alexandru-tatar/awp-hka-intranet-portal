---
name: 01-verzeichnisstruktur
description: Verzeichnisstruktur, Schichten und Ablageregeln des HKA Portals (Python-Paket portal in src/portal, Design-Kit in kit/, Dev-Daten in dev/). Verwenden, sobald neue Dateien, Module, Routen, Templates, Manifeste oder Tests angelegt, verschoben oder eingeordnet werden – und bei der Frage "wo gehört das hin?".
---

# Verzeichnisstruktur und Schichten

Projekt `hka-portal` (Paket `portal`, Python ≥ 3.13, FastAPI + Jinja2, server-gerendertes HTML).
Spezifikationen: `02-gateway.md`, `03-registry.md`, `04-portal-ui-and-design-kit.md`, `05-adapter-service.md` u. a. im Ordner `claude-proposal/`.

## Kompletter Baum

```text
intranet-portal/
├── pyproject.toml                  # Paket "hka-portal", Dependencies (gepinnt), Gruppe dev, pytest-Konfiguration, package-data
├── Dockerfile, Dockerfile.trixie   # Portal-Image: dhi.io (hardened) bzw. Debian Trixie ohne Login; .dockerignore
├── extras/compose/                 # Docker Compose je Baustein
│   ├── redis/compose.yml           # Sessions (:6379)
│   ├── keycloak/                   # compose.yml, Dockerfile (+ .dockerignore), hka-realm.json, theme/hka/login (Login-Seite im Portal-Look), dev-IdP :8180
│   ├── backend/compose.yml         # Portal-Container (Dockerfile.trixie, dev/gateway.compose.yml)
│   └── server/compose.yml          # include: redis + keycloak + backend → docker compose up startet alles
├── uv.lock                         # GENERIERT durch uv – nicht von Hand editieren
├── Makefile                        # setup · kit · contrast · dev · test
├── README.md                       # Start, Aufbau, "Eine App hinzufügen", Platzhalter-Tabelle
├── claude-proposal/                # Spezifikationen 02–10, Architekturvorschlag (Vorgabe, Quelle der Wahrheit, nicht editieren ohne Absprache)
├── docs/                           # Entwicklerdokumentation (docs/api/: Sphinx-Konfiguration, HTML nur aus Docstrings via make docs): index.md, 01 Architektur, 02 Entwicklung, 03 Service/Router, 04 Anmeldung, 05 Compose, 06 Oberfläche, 07 Registry und Apps
├── schemas/
│   └── manifest.schema.json        # Vertrag #2: ein Schema für Pipeline, Registry, SDK
├── kit/                            # Design-Kit (04 §11) – Details im Skill hka-design
│   ├── css/                        # tokens · base · layout · components · print · fonts
│   ├── js/kit.js                   # Dialog-Muster, ≤ 1 KB (Build prüft)
│   ├── icons/icons.svg             # Icon-Allow-List = enum menu.icon im Schema
│   ├── fonts/                      # IBM Plex (OFL), selbst gehostet
│   ├── pairs.json                  # Farbpaare fürs Kontrast-Gate
│   ├── tools/build.py, contrast.py # Build + Kontrast-Gate (bricht Build ab)
│   ├── VERSION
│   └── dist/                       # GENERIERT: kit-<hash>.css/js, icons-<hash>.svg, fonts/, kit-manifest.json
├── src/portal/
│   ├── __init__.py
│   ├── app.py                      # create_app(): NUR Verdrahtung (Context, Static, Middleware, Router)
│   ├── dev.py                      # ASGI-Einstieg: uvicorn portal.dev:app
│   ├── context.py                  # build_portal(): Config, Kit, Texte, Registry, Sessions, Views
│   ├── core/                       # config · i18n · kit (Asset-URLs, STATIC_PREFIX) · log (Logging-Einrichtung)
│   ├── service/                    # Geschäftslogik, Rückgabe nur als DTO (siehe Regeln unten)
│   │   ├── __init__.py             # Re-Exports + __all__
│   │   ├── exceptions.py           # NotFoundError, LoginRequiredError, LoginFailedError, ForbiddenError, UnavailableError, InvalidCsrfError, UnknownUserError
│   │   ├── app_dto.py              # AppDTO, NavGroupDTO
│   │   ├── app_service.py          # AppService(Registry): find_nav_groups, find_all, find_authorized
│   │   ├── login_service.py        # LoginService(oidc, login_store, role_mapper, sessions): start, finish
│   │   ├── session_dto.py          # SessionDTO
│   │   ├── session_service.py      # SessionService(MemorySessionStore): find_by_id
│   │   └── session_write_service.py # SessionWriteService(store, dev_users): create, delete
│   ├── registry/                   # models · validation (Manifest) · sources (RegistrySource) · store (Snapshot)
│   ├── auth/                       # sessions (Protocol SessionStore + Memory) · redis_sessions (RedisSessionStore, RedisLoginStore) · oidc (OidcClient) · roles (RoleMapper) · dev_users · redirects
│   ├── web/                        # views (Rendern) · menu (current_slug) · deps (Session/Rolle/Service-Dependencies) · errors · middleware
│   ├── router/                     # HTTP-Schnittstelle, ein APIRouter pro Datei
│   │   ├── __init__.py             # Re-Exports (page_router, auth_router, nav_router, dev_router) + __all__
│   │   ├── constants.py            # ETAG, IF_NONE_MATCH, CACHE_CONTROL, X_PORTAL_KIT, ...
│   │   ├── page_router.py          # /, /_portal/status, /_portal/connections, /_portal/error/{code}
│   │   ├── auth_router.py          # /logout (GET Bestätigung, POST mit CSRF)
│   │   ├── nav_router.py           # /nav mit ETag
│   │   ├── health_router.py        # /readyz (Redis-Ping, 503 bei Ausfall)
│   │   ├── oidc_router.py          # /login, /oidc/callback (nur auth_mode: oidc)
│   │   ├── dev_login_router.py     # /login Testpersonen-Auswahl (nur auth_mode: dev)
│   │   └── dev_router.py           # /apps/{slug}/ Platzhalter (nur env: dev)
│   ├── locales/messages.de.yml     # ALLE UI-Texte
│   └── templates/
│       ├── base.html
│       ├── partials/               # header · nav · footer
│       ├── pages/                  # home · status · connections · error · logout · dev_login · dev_app
│       └── macros/                 # fields · dialog · table
├── dev/                            # nur lokale Entwicklung
│   ├── gateway.dev.yml             # Konfiguration lokal
│   ├── manifests/<slug>.json       # ein Manifest pro App  ← neue Apps hier anlegen
│   ├── state.yml                   # Status je App (healthy/unhealthy/…) bis es den Prober gibt
│   ├── users.yml                   # Testpersonen mit Rollen (auth_mode: dev)
│   ├── gateway.oidc.yml            # Konfiguration für Keycloak + Redis (auth_mode: oidc)
│   ├── roles.yml, grants.yml       # IdP-Claims → Rollen (02 §8), Rollen je Subject
│   ├── gateway.compose.yml         # Konfiguration fürs Backend im Container (redis, keycloak über Compose-Netz)
│   └── keycloak/portal-client-secret  # Client-Secret des dev-IdP (nur dev!)
└── tests/
    ├── conftest.py
    ├── test_kit.py                 # Kit, "kein Hex außerhalb tokens.css"
    ├── test_manifest.py            # Schema, Slugs, Rollen, Scopes
    ├── test_logging.py             # Logformat, Level je Logger, Request-ID, Umleitung des Standard-Loggings
    ├── test_errors.py              # Fehlerseiten für alle üblichen Status (HTML, nie JSON)
    ├── test_service.py             # Service-Schicht ohne HTTP
    ├── test_oidc.py                # OIDC-Login gegen gefälschten IdP + fakeredis (G2/G4/G6, Token-Prüfungen)
    └── test_portal_ui.py           # UI1–UI14, REG4/5
```

## Schichten

```text
   HTTP-Anfrage
        │
   ┌────▼─────────────────────────────┐
   │ router/   dünne Handler          │  page_router · auth_router · nav_router · dev_router
   └────┬─────────────────────────────┘
   ┌────▼─────────────────────────────┐
   │ web/      deps · views           │  Session/Rolle prüfen, Daten → Template-Kontext
   │           errors · middleware    │  errors.py: Service-Exceptions → HTTP-Status
   └────┬─────────────────────────────┘
   ┌────▼─────────────────────────────┐
   │ service/  AppService             │  Geschäftslogik, DTOs, fachliche Exceptions,
   │           SessionService         │  kein HTTP/FastAPI
   │           SessionWriteService    │
   └────┬───────────────┬─────────────┘
   ┌────▼────────┐  ┌───▼─────────────┐
   │ registry/   │  │ auth/           │  Daten-/Speicherzugriff (Repository-Rolle)
   │ models      │  │ sessions        │
   │ validation  │  │ dev_users       │
   │ sources     │  │ redirects       │
   │ store       │  └─────────────────┘
   └────┬────────┘
   ┌────▼─────────────────────────────┐
   │ core/    config · i18n · kit · log │  Grundlagen, hängt von nichts anderem im Paket ab
   └──────────────────────────────────┘
   templates/ + locales/ + kit/dist  ←  nur gelesen von web/views und StaticFiles
```

Abhängigkeitsrichtung von oben nach unten: `router → web → service → registry/auth → core`.
Nie umgekehrt (z. B. importiert `service/` nie aus `web/` oder `router/`, `registry/` nie aus `service/`).

## Wohin gehört was?

| Ich will … | Ablage |
|---|---|
| neue Seite | Handler in `router/page_router.py` (oder neue `<thema>_router.py` + Export in `router/__init__.py` + `include_router` in `app.py`), Template in `templates/pages/`, Texte in `locales/messages.de.yml` |
| neue App im Menü | `dev/manifests/<slug>.json` (Schema: `schemas/manifest.schema.json`); Status in `dev/state.yml` |
| neue Registry-Quelle (z. B. SQLite) | Klasse in `registry/sources.py` mit `load()` + `fingerprint()` (Protokoll `RegistrySource`) |
| Manifest-Regel | `registry/validation.py` (+ Schema, falls Feld neu) |
| neue Geschäftsregel | `service/<entity>_service.py` (lesen) bzw. `<entity>_write_service.py` (schreiben) |
| neuer Rückgabetyp eines Services | `service/<entity>_dto.py`, Export in `service/__init__.py` |
| neue fachliche Exception | `service/exceptions.py` + Status-Mapping in `web/errors.py` (`SERVICE_ERROR_STATUS`) |
| Service in Handler nutzen | `Depends`-Alias in `web/deps.py` (z. B. `AppServiceDep`), Instanz in `context.py` bauen |
| Session-/Rollen-Prüfung | `web/deps.py` |
| Fehlerseite / Statuscode-Mapping | `web/errors.py` |
| Header, CSP, ETag, `X-Portal-Kit` | `web/middleware.py` / `router/nav_router.py` (Header-Namen in `router/constants.py`) |
| Konfigurationswert | `core/config.py` (unbekannte Keys sind Fehler) + `dev/gateway.dev.yml` bzw. `dev/gateway.oidc.yml` |
| neue Rollenzuordnung vom IdP | `dev/roles.yml` (Claim → Rolle), `dev/grants.yml` (je Subject) |
| neuer Testbenutzer im dev-IdP | `extras/compose/keycloak/hka-realm.json`, danach `make idp-down idp-up` (baut das Image neu) |
| UI-Text | `locales/messages.de.yml` – nie im Template hartkodieren |
| wiederverwendbares HTML (Feld, Dialog, Tabelle) | `templates/macros/` |
| CSS / Farbe / Schrift / Icon | `kit/` (Tokens nur in `kit/css/tokens.css`), danach `make kit contrast` |
| Test | `tests/test_<thema>.py`, Fixtures in `tests/conftest.py` |
| nur-Dev-Funktion | `router/dev_router.py` (wird nur bei `cfg.dev` eingehängt) |

## Kernregeln

- **Doku mitführen:** `docs/` beschreibt den Ist-Zustand für künftige Entwickler (Architektur, Befehle, Konventionen, Anmeldung, Compose) – keine Historie und keine Begründungen von Entscheidungen. Ändert sich Verhalten, Struktur oder ein Befehl, wird das passende Kapitel im selben Zug angepasst. `claude-proposal/` ist Vorgabe und wird nicht geändert.
- **`app.py` bleibt reine Verdrahtung** – keine Logik, keine Handler.
- **Logging:** `from loguru import logger`, `logger.debug("key={}", value)`; eingerichtet wird es nur in `portal/dev.py` über `core/log.py` (Konfiguration im Abschnitt `logging` der YAML-Datei). Jede Zeile trägt die `request_id`.
- **Docstrings überall:** Jedes Modul, jede Klasse, Funktion und Methode in `src/portal` (auch private) bekommt einen deutschen Sphinx-reST-Docstring (`:param:`, `:return:`, `:rtype:`, `:raises:`, `:ivar:` bei Datenklassen). Verschachtelte Funktionen sind ausgenommen. Die Docstrings speisen Sphinx autodoc (`make docs`, Konfiguration in `docs/api/`, Build mit `-W`).
- **Router dünn**: Handler rufen Services (über `Annotated[<X>Service, Depends(...)]` aus `web/deps.py`) und rendern über `web/views`; keine Fachlogik im Handler.
- **Router-Datei**: `<thema>_router.py`, darin `router: Final = APIRouter(tags=["<Plural>"])`; Handler sind Funktionen (`@router.get/post`), keine Controller-Klassen, mit Rückgabetyp `Response`, reST-Docstring (Deutsch) und `logger.debug`.
- **Private Hilfsfunktionen** mit `_` am Dateiende, ohne Docstring; HTTP-Konstanten in `router/constants.py`.
- **Zwei Klassen pro Entity**: `<Entity>Service` (lesen) und `<Entity>WriteService` (schreiben); Repository (hier `Registry`, `MemorySessionStore`) kommt per Konstruktor als `self.repo`.
- **Services geben nur DTOs zurück** (`@dataclass(eq=False, slots=True, kw_only=True)` mit eigenem `__init__(self, <entity>)`, nur primitive Felder); Entities/`AppView`/`Session` verlassen `service/` nicht.
- **Nicht gefunden → `NotFoundError`** im Service; keine `HTTPException` aus `fastapi`/`starlette` in `service/`.
- **Docstrings in `service/`**: Deutsch, reST (`:param:`, `:return:`, `:rtype:`, `:raises:`), `Final` für lokale Konstanten, Logging mit `from loguru import logger` und `logger.debug("key={}", value)` (im ganzen Projekt, kein stdlib-`logging`).
- **Alle UI-Texte** nur in `locales/messages.de.yml`.
- **Kein Hex-Farbwert** außerhalb `kit/css/tokens.css` (Test erzwingt das).
- **Templates**: Seiten erben von `base.html`; Wiederkehrendes als Macro/Partial, nicht kopieren.
- **Neue Pakete** brauchen `__init__.py`; Templates/Locales sind über `package-data` in `pyproject.toml` eingebunden – neue Dateitypen dort ergänzen.
- **Dev-Daten** (`dev/`) enthalten nie Produktivwerte; Dev-Routen nur bei `env: dev`.
- **Eine Datei pro Thema**, Dateiname `snake_case`; Tests spiegeln das Thema, nicht die Dateistruktur 1:1.

## Generierte / nicht editierbare Dateien

| Datei/Ordner | Erzeugt durch |
|---|---|
| `kit/dist/` | `make kit` (`kit/tools/build.py`) – in `.gitignore` |
| `uv.lock` | `uv sync` / `uv lock` |
| `.venv/` | `make setup` (`uv sync`) |
| `docs/api/generated/`, `docs/api/_build/` | `make docs` (sphinx-apidoc, sphinx-build) |
| `src/hka_portal.egg-info/` | `uv sync` |
| `.pytest_cache/`, `__pycache__/` | Tools |

## Häufige Fehler

- Datei in `kit/dist/` von Hand ändern → wird beim nächsten Build überschrieben; Quelle in `kit/css|js|icons` ändern.
- Text direkt ins Template schreiben → gehört in `messages.de.yml`.
- Logik in `router/` oder `app.py` → nach `web/` bzw. `registry/`/`auth/` verschieben.
- Import von `web/` oder `router/` aus `registry/`, `auth/` oder `core/` → Schichtenverletzung.
- Neues Manifestfeld nur im Code ergänzen → zuerst `schemas/manifest.schema.json` (unbekannte Felder sind Fehler).
- Neues Icon in `icons.svg` ohne Eintrag im Schema-Enum `menu.icon` → Manifest wird abgelehnt.
