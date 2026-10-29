# 02 – Entwicklung

## Voraussetzungen

Python ≥ 3.13, [uv](https://docs.astral.sh/uv/), für Anmeldung und Container Docker.

## Befehle

| Befehl | Wirkung |
|---|---|
| `make setup` | `uv sync`: `.venv` und Abhängigkeiten aus `uv.lock` |
| `make dev` | baut das Kit, startet mit Testpersonen-Login auf `:8000` (`dev/gateway.dev.yml`) |
| `make dev-oidc` | wie `dev`, aber mit Keycloak + Redis (`dev/gateway.oidc.yml`); vorher `make idp-up` |
| `make idp-up` / `idp-down` | nur Redis und Keycloak als Container |
| `make server-up` / `server-down` | Redis, Keycloak und Backend als Container |
| `make kit` / `make contrast` | Design-Kit bauen / Kontrast-Gate |
| `make test` | Kontrast-Gate und pytest |
| `make docs` | API-Dokumentation als HTML aus den Docstrings: `docs/api/_build/html/index.html` |

Abhängigkeiten: `uv add <paket>` (Laufzeit), `uv add --dev <paket>` (nur Entwicklung). `PORT` ist mit
`make dev PORT=…` änderbar; bei `dev-oidc` muss er zur `redirect_uri` passen.

## Konfiguration

Eine YAML-Datei, Pfade relativ zur Datei. `PORTAL_CONFIG` wählt sie (Standard: `dev/gateway.dev.yml`).
Unbekannte Schlüssel brechen den Start ab. Schlüssel: `core/config.py`.

| Datei | Zweck |
|---|---|
| `dev/gateway.dev.yml` | Testpersonen (`auth_mode: dev`), Sessions im Speicher |
| `dev/gateway.oidc.yml` | Keycloak + Redis, Portal auf dem Host |
| `dev/gateway.compose.yml` | wie oben, Portal im Container (`redis`, `keycloak` als Hostnamen) |

## Tests

`pytest` unter `tests/`. `conftest.py` legt pro Test eine Kopie von `dev/` an, sodass Manifeste frei verändert werden
können. Für die Anmeldung gibt es einen gefälschten IdP und `fakeredis` (`tests/test_oidc.py`), es wird weder Keycloak
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
| `test_oidc.py` | Anmeldung, Sessions in Redis, Abmeldung, Token-Prüfung |
| `test_kit.py` | Kontrast-Gate, Kit-Build, keine Hex-Farben außerhalb der Tokens |
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
    redis: INFO
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
