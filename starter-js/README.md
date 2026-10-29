# starter-js

**Zweck:** Golden Master für JavaScript-Apps (Express): eine leere App mit Health-Endpunkt, Jest-Test und ESLint. Auf dieser Grundlage bauen Fachkräfte ihre Micro-Apps.
**Verantwortlich:** [Name] · **Stand:** 26.10.2026 · **Phase:** 1 (Grundlagen)

## Voraussetzungen
- Node.js **24 oder neuer** (lokal getestet mit Node 26), npm
- Git; Docker ist nur für `make docker` nötig
- Zugang zur GitLab-Gruppe der HKA (nach Klärung)

## Schnellstart

```bash
npm install     # einmalig: Abhängigkeiten laden
make dev        # lokal starten, startet bei Änderungen neu (http://localhost:8080/healthz)
make start      # wie im Betrieb starten
make test       # automatische Tests (Jest)
make lint       # Stil- und Fehlerprüfung (ESLint)
make docker     # als Container bauen, genau wie in der Pipeline
```

Die fünf Befehle sind in allen Startern gleich (`dev`, `start`, `test`, `lint`, `docker`). Der Port lässt sich mit `PORT=…` ändern (Standard 8080).

## Aufbau

```text
src/app.js            Express-App (createApp) mit GET /healthz
src/server.js         startet den Server, beendet sich geordnet bei SIGTERM
src/healthcheck.js    Gesundheitstest für den Container (nur Standardbibliothek)
tests/health.test.js  Jest-Tests für den Health-Endpunkt
eslint.config.js      ESLint (Flat Config, CommonJS)
Makefile              die fünf Befehle
Dockerfile            Container-Abbild (ohne Administratorrechte, mit HEALTHCHECK)
```

## Qualität
- Der Starter erfüllt die **Starter-Konvention** (`team-docs/entwicklung/starter-konvention.md`); geprüft mit `tools/check-starter.py` im Ordner `pipeline-templates/` (Stand 26.10.2026: 28 von 28 Prüfpunkten).
- Pull Requests brauchen **eine Freigabe einer zweiten Person** und eine grüne Pipeline.
- Rote Prüfung sperrt den Merge.

## Entscheidungen

| Datum | Entscheidung | Grund |
|---|---|---|
| 26.10.2026 | **Jest** als Testwerkzeug | Angebot §9.1 nennt Jest für JavaScript |
| 26.10.2026 | **CommonJS** statt ES-Module | Jest 30 führt ES-Module nur mit `NODE_OPTIONS=--experimental-vm-modules` aus (lokal geprüft: ohne Schalter schlägt der Test fehl, mit Schalter läuft er mit „experimental"-Warnung). CommonJS läuft ohne Zusätze. Beim Wechsel zu ES-Modulen oder `node --test` ändern sich nur `package.json`, `eslint.config.js` und die Tests. |
| 26.10.2026 | Node ≥ 24 (`engines`) | aktuelle Langzeitversion; lokal Node 26 |
| 26.10.2026 | Gesundheitstest über `src/healthcheck.js` | im schlanken Abbild gibt es kein `curl` |

## Betrieb
- Gesundheitstest: `GET /healthz` antwortet mit `200` und `{"status":"ok"}`; **nicht verändern**.
- Das **Dockerfile wurde am 26.10.2026 gebaut und geprüft** (Docker 29.9, Compose 5.6): Bauzeit 7 s, läuft als Benutzer `10001`, Gesundheitstest vorhanden und nach 5 s „healthy", `GET /healthz` → 200, schreibgeschütztes Dateisystem und `--cap-drop ALL` funktionieren, `docker stop` beendet mit Exit 0. Mit `docker compose up --wait` wird der Gesundheitstest des Abbilds berücksichtigt.
- **Noch offen:** das Basisabbild `node:24-bookworm-slim` vor der Freigabe per Digest festlegen; Bau in der Pipeline (Podman/Runner) wurde nicht geprüft.

## Änderungsprotokoll

| Datum | Änderung | Ticket |
|---|---|---|
| 26.10.2026 | Leere Express-App mit Health-Endpunkt, Jest, ESLint, Makefile, Dockerfile | HKA-26 |
| 26.10.2026 | Dockerfile gebaut und lokal geprüft (Gesundheitstest, nicht-root, schreibgeschützt) | HKA-26 |
| 26.10.2026 | Starter-Konvention und automatische Prüfung (28/28 bestanden) | HKA-26 |
