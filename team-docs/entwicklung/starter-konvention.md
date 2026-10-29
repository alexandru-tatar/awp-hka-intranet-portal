# Starter-Konvention (Phase 1)

*Status: Entwurf zur Abstimmung · Version 0.1 · Stand 26.10.2026 · Verantwortlich: [Name] · Abzustimmen mit den Verantwortlichen beider Starter*

## Zweck

Es gibt zwei Starter (Python/FastAPI und JavaScript/Express). Sie sollen sich für Fachkräfte und für die KI **gleich anfühlen**: dieselben Ordner, dieselben fünf Befehle, derselbe Gesundheitstest, dieselben Container-Regeln. Diese Seite legt fest, **was gleich sein muss** und **was sich unterscheiden darf**. Ob ein Starter sich daran hält, prüft ein Skript (Abschnitt 6) — nicht eine Person, die beide Starter besitzt.

Dies ist ein **Vorschlag**. Weicht ein Starter ab, wird die Abweichung in Abschnitt 5 eingetragen, nicht stillschweigend im Code gelöst.

## 1. Pflichtbestandteile in Phase 1

| Bestandteil | Regel | Prüfung |
|---|---|---|
| Ordner | `src/` (Anwendungscode) und `tests/` (Tests) | Struktur |
| Dateien | `README.md`, `Makefile`, `Dockerfile`, `.dockerignore`, `.gitignore`, `.editorconfig` | Struktur |
| Fünf Befehle | `make dev`, `make start`, `make test`, `make lint`, `make docker` — Namen in beiden Startern gleich; das `Makefile` unterscheidet sich nur in der Zeile `RUNNER` | Makefile |
| Qualität | `lint` und `test` laufen ohne Fehler; **dieselben Befehle** führt die Pipeline aus | Pipeline |
| Gesundheitstest | `GET /healthz` antwortet mit Status `200` und genau `{"status":"ok"}`; keine Anmeldung nötig | Container |
| Port | die App hört auf `0.0.0.0` und dem Port aus der Umgebungsvariable `PORT`, Standard **8080** | Container |
| Container: Benutzer | läuft als Benutzer **`10001:10001`** (numerisch), nicht als Administrator | Container |
| Container: Gesundheitstest | das Abbild enthält einen `HEALTHCHECK`, der **ohne `curl`** auskommt (Standardbibliothek der Sprache) | Container |
| Container: Härtung | läuft mit schreibgeschütztem Dateisystem (Schreiben nur nach `/tmp` oder `/data`) und ohne zusätzliche Fähigkeiten (`--cap-drop ALL`, `no-new-privileges`) | Container |
| Container: Beenden | endet bei `docker stop` (SIGTERM) geordnet mit Exit-Code 0 | Container |

## 2. Was sich unterscheiden darf

| Thema | Python | JavaScript |
|---|---|---|
| Framework | FastAPI | Express |
| Lint | Ruff | ESLint |
| Test | pytest | Jest (Angebot §9.1) |
| Ausführung der Befehle | `RUNNER := poe` (oder gleichwertig) | `RUNNER := npm run` |
| Abhängigkeiten | `pyproject.toml` / `requirements*.txt` | `package.json` + `package-lock.json` |
| Unterstruktur von `src/` | sprachüblich (z. B. `src/app/`) | sprachüblich (z. B. `src/app.js`) |
| Gesundheitstest im Abbild | Python-Skript | Node-Skript |
| Basisabbild | `python:3.12-slim` (Digest vor Freigabe festlegen) | `node:24-bookworm-slim` (Digest vor Freigabe festlegen) |

## 3. Was in Phase 2 dazukommt (noch nicht geprüft)

`manifest.json`, `AGENTS.md`, `.agents/skills/`, `.devcontainer/`, `platform_sdk/`, Prüfskript und Konformitätsprüfung der Pipeline. Bis dahin enthält ein Starter nur die Bestandteile aus Abschnitt 1.

## 4. Begründung der Container-Regeln

Die Plattform startet jede App als eigenen Container mit festen Grenzen (kein Administrator, schreibgeschützt, keine zusätzlichen Rechte, Gesundheitstest). Eine App, die das in der Entwicklung nicht aushält, würde erst im Betrieb scheitern. Deshalb gelten die Regeln schon für die leeren Starter.

## 5. Eingetragene Abweichungen

| Datum | Starter | Abweichung | Grund | Entscheidung |
|---|---|---|---|---|
| | | | | |

## 6. Prüfen

Voraussetzungen: Python 3, Docker (für die Container-Prüfung), Internetzugang für Paketquellen. Aufruf im Ordner `pipeline-templates/`:

```bash
python3 tools/check-starter.py ../starter-js
python3 tools/check-starter.py ../starter-python
python3 tools/check-starter.py ../starter-js --skip container      # ohne Docker
```

Das Skript prüft vier Gruppen — **Struktur**, **Makefile**, **Pipeline** (Lint und Test wie in der Pipeline) und **Container** — und gibt je Prüfpunkt den gefundenen Wert aus. Es endet nur dann mit Exit-Code 0, wenn alle gewählten Prüfungen bestehen.

## 7. Offene Punkte

- Genaue Ordnerstruktur innerhalb von `src/` (bewusst nicht festgelegt, solange beide Starter gleiche Pflichtbestandteile haben).
- Ob `make dev` im Container-Betrieb (Dev Container) zusätzlich geprüft werden soll (ab Phase 2).
- Festlegung der Basisabbilder per Digest vor der Freigabe.
