# Verzeichnisstruktur und Schichten

## Kompletter Baum

```text
fastapi-template/
├── pyproject.toml                  # uv-Projekt "mitglied": Dependencies, Gruppen dev/doc/lint, ruff, pytest, ty
├── uv.lock                         # GENERIERT durch uv – nicht von Hand editieren
├── Dockerfile                      # Multi-Stage-Build, "hardened" Image (dhi), ENTRYPOINT python -m mitglied
├── Dockerfile.alpine               # Variante mit Alpine
├── Dockerfile.trixie               # Variante mit Debian Trixie
├── docker-bake.hcl                 # docker buildx bake für die Image-Varianten
├── mkdocs.yml                      # Doku mit mkdocs-material + mkdocstrings
├── sonar-scanner.py                # Aufruf SonarQube-Scanner
├── .editorconfig                   # utf-8, LF, 4 Spaces, max_line_length = 88
├── .github/workflows/ci.yml        # CI: ruff check src, ruff format src --check
├── README.md, README.install.md, VORGEHENSWEISE.md
├── docs/                           # mkdocs-Quellen
│   ├── index.md, use-cases.md, komponentendiagramm.md, schichtenarchitektur.md, er-diagramm.md
│   ├── diagramme/src/*.plantuml    # PlantUML-Quellen
│   └── modules/*.md                # je Schicht "::: mitglied.<paket>" für mkdocstrings
├── extras/
│   ├── bruno/fastapi-appserver/    # Bruno-Collection (REST + GraphQL Requests)
│   ├── compose/                    # Docker Compose: backend, postgres, keycloak, mailpit, mitglied, ...
│   │   └── postgres/init/mitglied/
│   │       ├── csv/mitglied.csv    # Testdaten (auch von DbPopulateService geladen)
│   │       ├── csv/ausweis.csv
│   │       ├── csv/ausleihe.csv
│   │       └── sql/create-db.sql, create-schema.sql
│   ├── dependency-check.py, suppression.xml   # OWASP Dependency Check
├── src/mitglied/
│   ├── __init__.py                 # exportiert app, main() -> run()
│   ├── __main__.py                 # python -m mitglied
│   ├── asgi_server.py              # run(): uvicorn mit TLS
│   ├── fastapi_app.py              # FastAPI-App: lifespan, Middleware, include_router, exception_handler
│   ├── problem_details.py          # create_problem_details() gemäß RFC 7807
│   ├── config/
│   │   ├── __init__.py             # Re-Export aller Konfigurationswerte
│   │   ├── config.py               # app_config aus resources/app.toml
│   │   ├── db.py                   # db_url, db_url_admin, db_connect_args, db_log_statements
│   │   ├── dev_modus.py            # dev_db_populate, dev_keycloak_populate
│   │   ├── excel.py, graphql.py, keycloak.py, logger.py, mail.py, server.py, tls.py
│   │   ├── dev/
│   │   │   ├── db_populate.py      # DbPopulateService: drop.sql, create.sql, CSV per COPY
│   │   │   ├── db_populate_router.py        # POST /db_populate (nicht eingehängt)
│   │   │   ├── keycloak_populate.py         # KeycloakPopulateService
│   │   │   └── keycloak_populate_router.py  # POST /keycloak_populate (nicht eingehängt)
│   │   └── resources/
│   │       ├── app.toml            # zentrale Konfiguration
│   │       ├── postgresql/create.sql, drop.sql, server.crt
│   │       └── tls/certificate.crt, key.pem
│   ├── entity/                     # SQLAlchemy-Entities + Enums
│   │   ├── __init__.py, base.py, mitglied.py, ausweis.py, ausleihe.py
│   │   └── geschlecht.py, mitgliedsstatus.py, interesse.py
│   ├── repository/                 # DB-Zugriff
│   │   ├── __init__.py, mitglied_repository.py
│   │   ├── pageable.py, slice.py   # generische Pagination
│   │   └── session_factory.py      # engine, Session
│   ├── service/                    # Geschäftslogik
│   │   ├── __init__.py, exceptions.py
│   │   ├── mitglied_dto.py
│   │   ├── mitglied_service.py     # lesen
│   │   └── mitglied_write_service.py  # schreiben
│   ├── router/                     # REST-Schnittstelle
│   │   ├── __init__.py, constants.py, dependencies.py, page.py
│   │   ├── mitglied_router.py      # GET
│   │   ├── mitglied_write_router.py   # POST, PUT
│   │   ├── mitglied_update_model.py, mitglied_model.py   # Pydantic
│   │   └── ausweis_model.py, ausleihe_model.py           # Pydantic für Kind-Entities
│   ├── graphql_api/
│   │   ├── __init__.py, graphql_types.py, schema.py
│   ├── security/                   # Keycloak, Rollen, Login
│   │   ├── __init__.py, auth_router.py, dependencies.py, exceptions.py, login_data.py
│   │   ├── response_headers.py, role.py, roles_required.py
│   │   └── token_service.py, user.py, user_service.py
│   └── static/favicon.ico
└── tests/
    ├── integration/
    │   ├── certificate.crt         # für verify=ctx
    │   ├── common_test.py          # URLs, login(), ctx
    │   ├── rest/conftest.py, get_by_id_test.py
    │   └── graphql_api/conftest.py, query_test.py
    └── lasttest/locustfile.py, README.md
```

## Schichten-Diagramm

```text
            HTTP (REST)                         HTTP (GraphQL)
                 │                                     │
   ┌─────────────▼──────────────┐      ┌───────────────▼──────────────┐
   │ router/                    │      │ graphql_api/                 │
   │  mitglied_router (GET)     │      │  schema.py: Query, Mutation  │
   │  mitglied_write_router     │      │  graphql_types.py            │
   │  *_model.py (Pydantic)     │      └───────┬──────────────┬───────┘
   │  dependencies.py (Depends) │              │ (Mutation)   │ (Query: direkt!)
   └─────────────┬──────────────┘              │              │
                 │  RolesRequired (security/)  │              │
   ┌─────────────▼─────────────────────────────▼──┐           │
   │ service/                                      │           │
   │  MitgliedService / MitgliedWriteService       │           │
   │  MitgliedDTO, exceptions.py                   │           │
   │  with Session() as session: ... commit()      │           │
   └─────────────┬─────────────────────────────────┘           │
   ┌─────────────▼─────────────────────────────────────────────▼──┐
   │ repository/  MitgliedRepository, Pageable, Slice, Session     │
   └─────────────┬─────────────────────────────────────────────────┘
   ┌─────────────▼──────────────┐
   │ entity/  Base, Mitglied,   │  ◄── config/ (app.toml)
   │  Ausweis, Ausleihe, Enums  │
   └─────────────┬──────────────┘
                 ▼
            PostgreSQL (psycopg, TLS verify-full)
```

Abhängigkeitsrichtung strikt von oben nach unten. Exceptions aus `service/` werden in
`fastapi_app.py` in HTTP-Statuscodes übersetzt (siehe `09-fehlerbehandlung.md`).

## Kernregeln

- **Eine Datei pro Klasse/Thema** je Schichtordner, Dateiname = `snake_case` der Klasse
  (`mitglied_repository.py` → `MitgliedRepository`).
- **Lesen und Schreiben getrennt**: `<entity>_service.py` / `<entity>_write_service.py`,
  `<entity>_router.py` / `<entity>_write_router.py`.
- **Pydantic-Models liegen in `router/`**, nicht in einem `schemas/`-Ordner.
- **DTO liegt in `service/`** und ist zugleich Strawberry-Typ.
- **Jedes Paket hat `__init__.py`** mit Docstring, Re-Exports und `__all__`.
- **Session wird im Service geöffnet** (`with Session() as session:`) und an jede
  Repository-Methode als Parameter `session` übergeben.
- **Router geben `Response`/`JSONResponse` zurück**, kein `response_model`.
- **Alles synchron** (`def`, nicht `async def`) – Ausnahme: `lifespan` und
  `request_body_to_dict` in `auth_router.py`.
- Konfiguration nur über `config/resources/app.toml` + `config/<thema>.py`.

## Generierte / nicht editierbare Dateien

| Datei/Ordner | Erzeugt durch |
|---|---|
| `uv.lock` | `uv sync` / `uv lock` |
| `.venv/` | `uv sync --all-groups` |
| `report.html`, `htmlcov/`, `.coverage` | `uv run pytest` (`--html`, `--cov`) |
| `log/app.log` | loguru (`config_logger`, derzeit nicht aufgerufen) |
| `site/` | `uv run mkdocs build` |
| `docs/diagramme/out` | mkdocs-build-plantuml-plugin |
| `.ruff_cache/`, `.pytest_cache/`, `__pycache__/` | Tools |
| `src/mitglied/config/resources/tls/*`, `postgresql/server.crt` | extern erzeugte Zertifikate – nur ersetzen, nicht editieren |

## Häufige Fehler

- Neuen Feature-Ordner `src/mitglied/<entity>/` anlegen → falsch, Dateien in die
  bestehenden Schichtordner legen.
- Pydantic-Model nach `service/` oder `entity/` legen → gehört nach `router/`.
- Neue Datei ohne Eintrag in `__init__.py`/`__all__` → Import über das Paket schlägt fehl.
