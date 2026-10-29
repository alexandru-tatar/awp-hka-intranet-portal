# pipeline-templates

**Zweck:** Zentrale Pipeline-Vorlage für alle App-Projekte der Micro-App-Plattform. Phase 1 enthält die Stufen **Lint** und **Test** für Python (Ruff, pytest) und JavaScript (ESLint, Jest). Eine rote Prüfung sperrt den Merge.
**Verantwortlich:** [Name] · **Stand:** 26.10.2026 · **Phase:** 1 (Grundlagen)

## Inhalt

| Datei | Aufgabe |
|---|---|
| `app-pipeline.yml` | die Pipeline (Stufen `lint`, `test`; Jobs wählen sich über vorhandene Dateien: `pyproject.toml`/`requirements.txt` → Python, `package.json` → JavaScript) |
| `ci-local.py` | führt **dieselben Befehle** der Pipeline lokal aus (ohne GitLab, ohne Container) |
| `tests/selftest.sh` | Selbsttest: grüne Fälle müssen bestehen, rote Fälle müssen scheitern |
| `tools/check-starter.py` | prüft einen Starter gegen die Starter-Konvention: Struktur, Makefile-Ziele, Lint/Test wie in der Pipeline, Container (Bau, Benutzer 10001, HEALTHCHECK, gehärteter Lauf, `/healthz`, geordnetes Beenden) |
| `tests/selftest-starter-check.sh` | Selbsttest der Prüfung: zwei gute Starter müssen bestehen, acht absichtlich kaputte Varianten müssen an der **erwarteten** Prüfung scheitern |
| `tests/fixtures/` | drei kleine Python-Beispiele (grün, Lint-Fehler, Test-Fehler) und `starter-python-example` (Beispiel für die Prüfung der Starter-Konvention; **kein** Starter und nicht das Ergebnis von HKA-25) |

Die **Werkzeugversionen stehen in der Pipeline** (`RUFF_VERSION`, `PYTEST_VERSION`), nicht in den App-Projekten; so kann eine App die Prüfung nicht durch eine andere Version abschwächen.

## Lokal prüfen

```bash
python3 ci-local.py ../starter-js                 # alle passenden Jobs für ein Projekt
python3 ci-local.py ../starter-js --only lint:js  # einzelne Jobs
tests/selftest.sh ../starter-js                   # sechs Fälle: grün/rot für Python und JavaScript
```

Voraussetzungen: Python 3 mit PyYAML, Node.js, Internetzugang für `pip`/`npm`. Jeder Job läuft in einer frischen Kopie des Projekts (ohne `node_modules`/`.venv`), wie ein neuer Checkout.

**Grenzen:** Die Befehle laufen auf dem eigenen Rechner, **nicht** im Container-Abbild (`image:`); Python-/Node-Versionen können abweichen. Nicht nachgebildet: Cache, Artefakte, Merge-Request-Pipelines, Regeln mit `if:`, Berechtigungen. Der lokale Lauf ersetzt **nicht** den Lauf in GitLab.

## Einbinden (nach Klärung des GitLab-Repositories)

1. Dieses Repository in der GitLab-Gruppe anlegen; Stand mit Tag `v1` versehen.
2. **Weg A (empfohlen):** im App-Projekt unter *Einstellungen → CI/CD → Allgemeine Pipelines → CI/CD-Konfigurationsdatei* eintragen: `app-pipeline.yml@<gruppe>/pipeline-templates:v1`. Vermutlich können Autorinnen und Autoren mit der Rolle *Developer* diese Einstellung nicht ändern (**Annahme — am Donnerstag bestätigen**).
3. **Weg B (falls Weg A nicht möglich ist):** in der `.gitlab-ci.yml` des Projekts

```yaml
include:
  - project: "<gruppe>/pipeline-templates"
    ref: v1
    file: app-pipeline.yml
```

4. Projekteinstellung *Merge-Requests → Pipelines müssen erfolgreich sein* aktivieren.

## Am Donnerstag in GitLab prüfen (nicht verifiziert)

| Punkt | Warum |
|---|---|
| Die Datei besteht den **CI-Lint** von GitLab (Editor *Pipeline → Lint*) | wurde bisher nur als YAML geparst und lokal ausgeführt |
| Welche **Runner** gibt es, welcher Executor? | die Jobs setzen `image:` voraus (Docker-Executor); bei Shell-Runnern fehlen Python/Node-Versionen |
| Verlangen die Runner **Tags**? | die Jobs haben keine Tags; sonst `tags:` ergänzen |
| Funktionieren `extends`, `rules:exists`, `cache:key:files` und die Einstellung „CI/CD-Konfigurationsdatei" in der vorhandenen **Ausprägung** (Community/Enterprise)? | die Vorlage nutzt nur Funktionen ohne kostenpflichtige Stufe — das ist eine Annahme |
| Zugang zu **Paketquellen** (`pip`, `npm`) aus den Runnern? | ohne Zugang scheitern die Installationsschritte |
| Gibt es `package-lock.json` im JavaScript-Projekt? | `npm ci` braucht sie |

## Starter prüfen

```bash
python3 tools/check-starter.py ../starter-js                    # alles (Container-Prüfung braucht Docker, z. B. `colima start`)
python3 tools/check-starter.py ../starter-python --skip container
tests/selftest-starter-check.sh ../starter-js                   # Selbsttest der Prüfung (ca. 2 Minuten)
```
Grundlage: `team-docs/entwicklung/starter-konvention.md`. Stand 26.10.2026: `starter-js` besteht 28 von 28 Prüfpunkten; der Python-Beispielstarter ebenso. Der echte Python-Starter (HKA-25) ist noch nicht geprüft.

## Versionierung
Änderungen laufen über Merge-Requests (eine Freigabe, Pipeline grün). Rückwärtskompatible Korrekturen wandern auf das bewegliche Tag `v1`; ein brechender Wechsel wird `v2` mit Hinweis für alle Projekte.

## Nicht in Phase 1
Geheimnis-Suche, Manifest-Prüfung, Container-Bau, Konformitätsprüfung und Bereitstellung kommen im Durchstich (Phase 2).
