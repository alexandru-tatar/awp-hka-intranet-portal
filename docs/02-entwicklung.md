# 02 – Entwicklung

## Voraussetzungen

Python ≥ 3.13, [uv](https://docs.astral.sh/uv/), für Anmeldung und Container Docker.

## Befehle

| Befehl | Wirkung |
|---|---|
| `make setup` | `uv sync`: `.venv` und Abhängigkeiten aus `uv.lock` |
| `make dev` | baut das Kit, startet mit Testpersonen-Login auf `:8000` (`dev/gateway.dev.yml`) |
| `make kit` / `make contrast` | Design-Kit bauen / Kontrast-Gate |
| `make test` | Kontrast-Gate und pytest |
| `make docs` | API-Dokumentation als HTML aus den Docstrings: `docs/api/_build/html/index.html` |

Abhängigkeiten: `uv add <paket>` (Laufzeit), `uv add --dev <paket>` (nur Entwicklung). `PORT` ist mit
`make dev PORT=…` änderbar.

## Konfiguration

Eine YAML-Datei, Pfade relativ zur Datei. `PORTAL_CONFIG` wählt sie (Standard: `dev/gateway.dev.yml`).
Unbekannte Schlüssel brechen den Start ab. Schlüssel: `core/config.py`.

| Datei | Zweck |
|---|---|
| `dev/gateway.dev.yml` | Testpersonen (`auth_mode: dev`), Sessions im Speicher |
| `dev/gateway.vm.yml` | Test-VM, `auth_mode: gateway` (Identität vom Security-Gateway) |

## Tests

`pytest` unter `tests/`. `conftest.py` legt pro Test eine Kopie von `dev/` an, sodass Manifeste frei verändert werden
können. Die Gateway-Identität (`tests/test_gateway_identity.py`) prüft signierte Test-Assertions, es wird weder Keycloak
noch Redis gebraucht.

Der `TestClient` von Starlette nutzt `httpx2`; deshalb liegt es in der Gruppe `dev`. Der Laufzeitcode (OIDC-Client) und die
Fake-IdP-Tests nutzen weiterhin `httpx`, beide Pakete sind unabhängig voneinander.

### Testdateien

| Datei | Prüft |
|---|---|
| `test_portal_ui.py` | Seiten, Menü, Logout, Zugriff auf Apps (IDs UI1 ff. aus 04 §12) |
| `test_errors.py` | Fehlerseiten für alle üblichen Status, nie JSON |
| `test_manifest.py` | Manifest-Prüfung und Registry-Quelle |
| `test_service.py` | Service-Schicht ohne HTTP |
| `test_gateway_identity.py` | Assertion-Prüfung, keine eigenen Sessions im Gateway-Modus, CSRF, Origin |
| `test_kit.py` | Kontrast-Gate, Kit-Build, keine Hex-Farben außerhalb der Tokens |
| `test_gateway.py` | Weiterleitung an Apps, Token, JWKS, `/nav` mit Token, Kit-Aliase (HKA-52, AK1 bis AK6) |
| `test_logging.py` | Logformat, Level je Logger, Request-ID in den Zeilen, Umleitung des Standard-Loggings |

## Konventionen

- **Logging:** `from loguru import logger`, `logger.debug("key={}", value)`; Aufbau und Konfiguration siehe Abschnitt „Logging".
- **Docstrings:** Jedes Modul, jede Klasse, Funktion und Methode (auch private; ausgenommen verschachtelte Funktionen)
  hat einen Docstring auf Deutsch im Sphinx-reST-Stil: `:param x:`, `:return:`, `:rtype:`, `:raises X:`, bei Datenklassen
  `:ivar x:`. Querverweise mit `:class:`, `:meth:`, `:mod:`; Code in doppelten Backticks. Die Docstrings sind die Quelle
  für die API-Dokumentation mit Sphinx autodoc.
- **Service und Router:** lokale Konstanten als `Final`. Details in [03](03-service-und-router.md).
- **Imports:** in `router/` absolut (`from portal.web.deps import …`), sonst relativ.
- **Texte:** Deutsch, in `messages.de.yml`.

## Logging

Eingerichtet wird es einmal beim Start in `portal/dev.py` (`configure_logging` in `core/log.py`), nicht beim Erzeugen der
Anwendung; Tests behalten dadurch ihre eigenen Ausgaben. Eine Konsolenzeile sieht so aus:

```text
2026-10-28T16:55:38.296+01:00 DEBUG    14812 --- [AnyIO worker th] portal.router.dev_login_router           : next=None [req=demo-42]
 Zeit mit Zeitzone              Level   PID       Thread (15)       Logger (auf 40 Zeichen gekürzt)           Meldung       Request-ID
```

- **Request-ID:** Jede Zeile, die während einer Anfrage entsteht, trägt deren `request_id` (`[req=…]`). Es ist dieselbe Nummer wie
  auf der Fehlerseite („Fehlernummer") und im Header `X-Request-Id`; so findet man zu einem Fehler alle zugehörigen Zeilen.
  Außerhalb von Anfragen steht `-`.
- **Zugriffszeile:** Das Portal schreibt sie selbst (`portal.web.middleware`), mit Request-ID und Dauer, z. B.
  `172.23.0.1:61070 - "GET /apps/noten/x HTTP/1.1" 404 (3.2 ms) [req=…]`. Die Zugriffszeile von uvicorn (`uvicorn.access`) ist dafür auf
  `WARNING` gestellt; Static-Dateien erscheinen nur auf `DEBUG`.
- **Standard-Logging:** Meldungen von uvicorn, httpx, redis u. a. laufen über denselben Weg und haben dasselbe Format.
- **Farben:** `color: auto` färbt nur auf einem Terminal, `always` immer (nötig für `docker logs` und die Run-Fenster mancher IDEs,
  die kein Terminal sind), `never` nie. Die Dev-Konfigurationen setzen `always`. Die Logdatei ist nie farbig.
- **Fehler:** `logger.exception(...)` schreibt den Traceback unter die Zeile.

Konfiguration im Abschnitt `logging` der YAML-Datei (`LoggingConfig`, Standard: Konsole `DEBUG` in dev, `INFO` in prod):

```yaml
logging:
  console_level: DEBUG
  color: always                  # auto | always | never
  file: /tmp/hka-portal.log      # optional; ohne Wert nur Konsole
  file_level: DEBUG
  rotation: 10 MB                # neue Datei ab dieser Größe
  retention: 3                   # so viele rotierte Dateien bleiben (als .gz)
  levels:                        # Mindestlevel je Logger (Modulname und alles darunter)
    portal.service: DEBUG
    uvicorn.access: WARNING
    httpx: WARNING
```

Unbekannte Schlüssel oder Level (erlaubt: `TRACE` bis `CRITICAL`) brechen den Start ab. Ein Eintrag unter `levels` gilt für die
Konsole und die Datei und hat Vorrang vor `console_level` und `file_level`.

## API-Dokumentation (Sphinx)

`make docs` erzeugt mit Sphinx autodoc das HTML ausschließlich aus den Docstrings in `src/portal`; die Markdown-Kapitel
in `docs/` sind nicht Teil davon. `sphinx-apidoc` legt eine Seite je Modul in `docs/api/generated/` an (nicht eingecheckt),
`docs/api/conf.py` und `docs/api/index.rst` sind die Konfiguration. Neue Module erscheinen automatisch. Der Build läuft mit
`-W`: Warnungen, etwa durch fehlerhaftes reST in einem Docstring, lassen ihn scheitern. `portal.dev` ist ausgenommen, weil
sein Import die Anwendung erzeugt. Sphinx liegt in der Abhängigkeitsgruppe `doc` (`uv add --group doc …`).

## Docker-Images

| Datei | Basis | Hinweis |
|---|---|---|
| `Dockerfile` | `dhi.io/python` (gehärtet) | `docker login dhi.io` nötig |
| `Dockerfile.trixie` | `python:3.14-slim-trixie` | ohne Login; wird vom Compose-Backend benutzt |

Beide bauen mit uv aus `uv.lock`, erzeugen das Design-Kit im Builder (`kit/dist/` ist nicht eingecheckt) und starten
als `nonroot` mit `python -m uvicorn portal.dev:app` auf Port 8000. Konfiguration im Image: `PORTAL_CONFIG`
(Standard `/opt/app/dev/gateway.dev.yml`).

```sh
docker build --file Dockerfile.trixie --tag hka/portal:0.1.0-trixie .
docker run --rm --publish 8000:8000 hka/portal:0.1.0-trixie
```

**Pipeline (HKA-57):** `.github/workflows/images.yml` baut `portal` (`Dockerfile`) für `linux/amd64`. Bei einem Pull
Request wird nur gebaut. Nach einem Merge auf `main` liegt das Image in `ghcr.io/alexandru-tatar/portal:<commit-sha>`;
der Digest steht in der Zusammenfassung des Laufs. Für dhi.io braucht das Repository die Secrets `DHI_USERNAME` und
`DHI_TOKEN`. Keycloak und Redis gehören zum Security-Gateway (`awp-hka-security-gateway`).

## Neue App anlegen

Das Portal legt neue Apps selbst an (HKA-82). Zwei Eingänge, dieselbe Logik (`service/app_creation_service.py`):

| Eingang | Adresse | Für wen |
|---|---|---|
| Portal-Seite „Neue App anlegen“ | `/_portal/neue-app`, Link „Neue App“ im Kopf | Fachkräfte mit der Rolle `app-creator` (und `platform-admin`) |
| JSON-Schnittstelle | `POST /_portal/api/apps` mit `{"slug", "language", "github_login"}` und dem Header `X-CSRF-Token` | Werkzeuge, die mit der Portal-Anmeldung arbeiten. Der Befehl in der Entwicklungsumgebung folgt (braucht eine Anmeldung ohne Browser im Security-Gateway) |

Wer darf: nur Personen mit einer Rolle aus `app_creation.creator_roles` (Standard `app-creator`, `platform-admin`). Alle anderen
bekommen 403. Die Rolle `app-creator` vergibt ein Admin auf der Verwaltungsseite als zusätzliche Rolle (Grants).

**Ablauf.** Alles, was nur liest, kommt zuerst; vor dem ersten Schreiben ist noch nichts entstanden:

1. Rolle, Slug (`^[a-z][a-z0-9-]{2,30}$`, nicht reserviert, nicht `meine-app` oder `andere-app`), Sprache und GitHub-Name prüfen.
2. Vorlage ist ein Template, das Repository `<owner>/app-<slug>` gibt es noch nicht.
3. Slug in der Registry reservieren (`Registrar.reserve`, Besitzer `<owner>/app-<slug>`). Ein vergebener oder gesperrter Name wird abgelehnt (PF-202).
4. Repository aus dem Golden Master anlegen, auf `manifest.json` warten, nur den Slug ersetzen, Zweig `develop`, Thema `hka-app`,
   Person einladen (Push-Recht), zuletzt das Ruleset `main-schutz` auf `main` (danach ist kein direkter Push mehr möglich).

Scheitert ein Schritt vor dem Anlegen, wird die Reservierung aufgehoben. Scheitert er danach, bleibt alles stehen und die Antwort
nennt Schritt und Repository (`created: true`); es wird nie automatisch gelöscht. Jede Anlage, Ablehnung und jeder Fehler steht
mit Person, Zeit und App in `app_creation.audit_file` (JSON-Zeilen) und im Log.

**Antworten der Schnittstelle** (immer JSON, kein Token, kein Schlüssel):

| Status | Antwort | Bedeutung |
|---|---|---|
| 201 | `{"slug", "repo", "url"}` | angelegt |
| 401 | `{"error": "login_required"}` | keine Anmeldung |
| 403 | `{"error": "forbidden"}` oder `{"error": "csrf"}` | falsche Rolle bzw. falsches CSRF-Token |
| 404 | `{"error": "disabled"}` | Abschnitt `app_creation` fehlt |
| 409 | `{"error": "slug_taken"}` | Name oder Repository vergeben, es wurde nichts angelegt |
| 422 | `{"error": "invalid", "field", "reason"}` | ungültige Eingabe |
| 502 | `{"error": "failed", "step", "created", "repo", "url"}` | ein Schritt ist gescheitert |

**Einrichten** (einmal, durch das Plattform-Team). Ohne den Abschnitt ist die Funktion aus (Seite und Schnittstelle 404):

1. GitHub App anlegen und im Konto bzw. in der Organisation der App-Repositories installieren. Die nötigen Rechte sind noch nicht
   geprüft; vermutlich Administration (anlegen, Rulesets, Einladungen), Contents (schreiben) und Metadata (lesen), eventuell Workflows,
   weil die Vorlage `.github/workflows/` enthält. Außerdem legt eine GitHub App Repositories vermutlich nur in einer Organisation an,
   nicht in einem persönlichen Konto. Beides vor der Einrichtung in der GitHub-Dokumentation prüfen (ADR zur Selbstbedienung).
2. Den privaten Schlüssel (PEM) als Docker-Secret auf den Server legen (`HKA_GITHUB_APP_KEY_SOURCE`, `docs/05-compose.md`). Er gehört nie
   in dieses Repository, in eine Antwort oder in ein Log.
3. In der Konfiguration den Abschnitt `app_creation` eintragen (Beispiel, auskommentiert, in `dev/gateway.dev.yml`) und `registry.owners_file` setzen.

**Nachweis für AK1 und AK2** (nur mit echter GitHub App, bisher nicht gelaufen): als Person mit der Rolle `app-creator` die Seite benutzen,
mit `curl` die Schnittstelle aufrufen und den Link des Repositorys in Jira festhalten. Erwartet: Repository mit `main`, `develop` und
Branchschutz auf `main`, Einladung an den angegebenen GitHub-Namen, Zeile im Protokoll.

Die Tests (`tests/test_app_creation.py`) laufen mit `make test` gegen ein erfundenes GitHub (`tests/fakes/fake_github.py`, `httpx.MockTransport`),
ohne echten Aufruf. `tools/neue-app.sh` ist veraltet (`tools/README.md`), seine Tests laufen weiter (`tests/test_neue_app.py`).
