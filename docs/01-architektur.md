# 01 – Architektur

Python-Paket `portal` (`src/portal`), FastAPI + Jinja2, serverseitig gerendertes HTML.

## Schichten

```text
router/    HTTP-Handler, dünn                      page · admin · app_creation · auth · nav · health · internal_registry · dev_login · dev
web/       deps · views · errors · middleware      Session/Rolle prüfen, Templates rendern, Exceptions → HTTP
service/   Geschäftslogik, DTOs, Exceptions        AppService · AdminService · AppCreationService · AuditLog · SessionService · SessionWriteService
registry/  Apps aus Manifesten                     models · validation · sources · store · registration
github/    GitHub-Zugriff als GitHub App           client (Schlüssel bleibt im Prozess, HKA-82)
auth/      Sessions (dev), Gateway-Identität, Grants  sessions · gateway · grants · dev_users · redirects
core/      Konfiguration, Texte, Kit-Assets, Logging  config · i18n · kit · log
```

Abhängigkeiten gehen nur nach unten. `service/` importiert nie aus `web/` oder `router/`, `core/` nie aus den
anderen Schichten. `github/` ist wie `registry/` und `auth/` Zugriffsschicht: `service/` darf es nutzen, es kennt nur `core/`. `context.py` baut aus der Konfiguration alle Objekte (`Portal`), `app.py` verdrahtet nur.

## Verzeichnisse

```text
src/portal/        Anwendung (siehe Schichten); locales/messages.de.yml und messages.en.yml = alle UI-Texte; templates/
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
| neue Seite | Handler in `router/<thema>_router.py` (+ Export in `router/__init__.py`, `include_router` in `app.py`), Template in `templates/pages/`, Texte in `locales/messages.de.yml` **und** `messages.en.yml` |
| neue Geschäftsregel | `service/<entity>_service.py` (lesen) bzw. `<entity>_write_service.py` (schreiben) |
| neue Rückgabestruktur eines Services | `service/<entity>_dto.py`, Export in `service/__init__.py` |
| neuer GitHub-Aufruf | Methode in `github/client.py` (Fehler nur als `GitHubError` mit Schritt und Status, nie mit Header oder Antworttext), Test gegen `tests/fakes/fake_github.py` |
| neue fachliche Exception | `service/exceptions.py` und Statuscode in `web/errors.py` (`SERVICE_ERROR_STATUS`) |
| neue App im Menü | lokal `dev/manifests/<slug>.json`, Status in `dev/state.yml`; auf der VM per `scp` kopiert und mit `sudo portal-deploy register` abgelegt (`python -m portal.registry`), der Prober setzt den Status |
| App auf der VM anzeigen oder entfernen | `sudo portal-deploy list` bzw. `remove <slug> --owner <owner/repo>` (`registry/registration.py`, Klasse `Registrar`); Status aus `registry.status_file`, die der Prober schreibt (`registry/status_file.py`) |
| Manifest-Regel oder -Feld | `registry/validation.py` und `schemas/manifest.schema.json` |
| neue Registry-Quelle | Klasse in `registry/sources.py` mit `load()` und `fingerprint()` (`RegistrySource`) |
| Konfigurationswert | `core/config.py` (unbekannte Keys sind Fehler) und die Dateien in `dev/` |
| Rollenzuordnung vom IdP | `dev/roles.yml` (Claim → Rolle), `dev/grants.yml` (je Subject) |
| wiederverwendbares HTML | `templates/macros/` (Feld, Dialog, Tabelle), `templates/partials/` |
| CSS, Farben, Schriften, Icons | `kit/` (Farbwerte nur in `kit/css/tokens.css`), danach `make kit contrast` |
| Funktion nur für Entwicklung | `router/dev_router.py` (nur bei `env: dev`) |
| Test | `tests/test_<thema>.py`, Fixtures in `tests/conftest.py` |

## Regeln

- Alle UI-Texte stehen in `messages.de.yml` und `messages.en.yml` (gleiche Schlüssel, ein Test prüft das), nicht in Templates.
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
| `/_portal/neue-app` | Rolle aus `app_creation.creator_roles` | Neue App anlegen (Formular, POST legt an); 404, wenn `app_creation` fehlt |
| `/_portal/api/apps` | Session + Rolle + `X-CSRF-Token` | Neue App anlegen als JSON (`docs/02-entwicklung.md`) |
| `/_portal/error/{code}` | – | Fehlerseite (HTML) mit dem angefragten Status 400–599, für die `errors`-Middleware von Traefik |
| `/nav` | Session (dev) bzw. Gateway-Assertion oder App-Token (`Authorization: Bearer`) | Menü-Fragment (ETag, `X-Portal-Kit`); ohne beides 401 als JSON für das SDK |
| `/login` | – | nur `auth_mode: dev`: Testpersonen-Auswahl (im Gateway-Modus 404, Login macht das Gateway) |
| `/sprache/{code}` | – | nur `auth_mode: dev`: Sprache `de`/`en` merken (Cookie `hka_lang`), 303 zurück zu `next`; unbekannter Code 404 (im Gateway-Modus macht das das Gateway) |
| `/logout` | Session | GET Bestätigung, POST mit CSRF-Token |
| `/readyz` | – | 200 |
| `/apps/<slug>/…` | Session + Rolle | nur `auth_mode: dev`: Platzhalter-Seite. Im Gateway-Modus routet das Gateway zur App (Portal: 404) |
