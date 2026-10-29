# 01 – Architektur

Python-Paket `portal` (`src/portal`), FastAPI + Jinja2, serverseitig gerendertes HTML.

## Schichten

```text
router/    HTTP-Handler, dünn                      page · auth · nav · health · oidc · dev_login · dev
web/       deps · views · errors · middleware      Session/Rolle prüfen, Templates rendern, Exceptions → HTTP
service/   Geschäftslogik, DTOs, Exceptions        AppService · SessionService · SessionWriteService · LoginService
registry/  Apps aus Manifesten                     models · validation · sources · store
auth/      Sessions, OIDC, Rollen                  sessions · redis_sessions · oidc · roles · dev_users · redirects
core/      Konfiguration, Texte, Kit-Assets, Logging  config · i18n · kit · log
```

Abhängigkeiten gehen nur nach unten. `service/` importiert nie aus `web/` oder `router/`, `core/` nie aus den
anderen Schichten. `context.py` baut aus der Konfiguration alle Objekte (`Portal`), `app.py` verdrahtet nur.

## Verzeichnisse

```text
src/portal/        Anwendung (siehe Schichten); locales/messages.de.yml = alle UI-Texte; templates/
kit/               Design-Kit (CSS, JS, Icons, Schriften); kit/dist/ wird generiert (make kit)
dev/               Konfigurationen, Manifeste, Testpersonen, Rollen für lokale Entwicklung
schemas/           manifest.schema.json
extras/compose/    Docker Compose je Dienst + server (alles)
tests/             pytest
claude-proposal/   Spezifikationen (Vorgabe)
docs/              diese Dokumentation (Markdown); docs/api/ = Sphinx-Konfiguration für die API-Doku aus den Docstrings
```

## Wohin gehört was?

| Aufgabe | Ort |
|---|---|
| neue Seite | Handler in `router/<thema>_router.py` (+ Export in `router/__init__.py`, `include_router` in `app.py`), Template in `templates/pages/`, Texte in `locales/messages.de.yml` |
| neue Geschäftsregel | `service/<entity>_service.py` (lesen) bzw. `<entity>_write_service.py` (schreiben) |
| neue Rückgabestruktur eines Services | `service/<entity>_dto.py`, Export in `service/__init__.py` |
| neue fachliche Exception | `service/exceptions.py` und Statuscode in `web/errors.py` (`SERVICE_ERROR_STATUS`) |
| neue App im Menü | `dev/manifests/<slug>.json`, Status in `dev/state.yml` |
| Manifest-Regel oder -Feld | `registry/validation.py` und `schemas/manifest.schema.json` |
| neue Registry-Quelle | Klasse in `registry/sources.py` mit `load()` und `fingerprint()` (`RegistrySource`) |
| Konfigurationswert | `core/config.py` (unbekannte Keys sind Fehler) und die Dateien in `dev/` |
| Rollenzuordnung vom IdP | `dev/roles.yml` (Claim → Rolle), `dev/grants.yml` (je Subject) |
| wiederverwendbares HTML | `templates/macros/` (Feld, Dialog, Tabelle), `templates/partials/` |
| CSS, Farben, Schriften, Icons | `kit/` (Farbwerte nur in `kit/css/tokens.css`), danach `make kit contrast` |
| Funktion nur für Entwicklung | `router/dev_router.py` (nur bei `env: dev`) |
| Test | `tests/test_<thema>.py`, Fixtures in `tests/conftest.py` |

## Regeln

- Alle UI-Texte stehen in `messages.de.yml`, nicht in Templates.
- Kein Hex-Farbwert außerhalb `kit/css/tokens.css` (ein Test erzwingt das).
- Jedes Paket hat `__init__.py`; Templates und Locales sind über `package-data` in `pyproject.toml` eingebunden.
- Generierte Dateien nicht von Hand ändern: `kit/dist/`, `uv.lock`, `.venv/`.
- Apps und Dev-Funktionen: `/apps/<slug>/` und `/login` mit Testpersonen existieren nur im Dev-Modus.

## Seiten und Routen

| Route | Zugriff | Zweck |
|---|---|---|
| `/` | Session | Startseite mit Menü |
| `/_portal/status` | `platform-admin` | Status aller Apps |
| `/_portal/connections` | Session | „Meine Verbindungen" |
| `/_portal/error/{code}` | – | Fehlerseite (HTML) mit dem angefragten Status 400–599, für die `errors`-Middleware von Traefik |
| `/nav` | Session | Menü-Fragment (ETag, `X-Portal-Kit`); ohne Session 401 als JSON für das SDK |
| `/login`, `/oidc/callback` | – | Anmeldung (OIDC) bzw. Testpersonen-Auswahl |
| `/logout` | Session | GET Bestätigung, POST mit CSRF-Token |
| `/readyz` | – | 200, oder 503 (JSON) wenn Redis nicht antwortet |
| `/apps/<slug>/` | Session + Rolle | Platzhalter-Seite (nur Dev) |
