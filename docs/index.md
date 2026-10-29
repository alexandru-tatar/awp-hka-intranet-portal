# HKA Portal – Entwicklerdokumentation

Portal-UI, Registry und Anmeldung des HKA Portals (Gateway-Teil). Die fachliche Vorgabe steht in
`../claude-proposal/` (Spezifikationen 02–10); diese Dokumentation beschreibt den **Ist-Zustand** der Umsetzung.

## Kapitel

| Kapitel | Inhalt |
|---|---|
| [01 Architektur](01-architektur.md) | Schichten, Verzeichnisstruktur, wohin neuer Code gehört |
| [02 Entwicklung](02-entwicklung.md) | Einrichten, Befehle, Tests, Konventionen, Docker-Images |
| [03 Service und Router](03-service-und-router.md) | Aufbau der Schichten, Feature hinzufügen, Fehlerbehandlung |
| [04 Anmeldung](04-anmeldung.md) | OIDC-Ablauf, Sessions in Redis, Rollen, Konfiguration, Umstieg auf prod |
| [05 Compose](05-compose.md) | Redis, Keycloak und Backend lokal starten, Fehlersuche |
| [06 Oberfläche](06-oberflaeche.md) | Templates, Makros, Texte, Fehlerseiten, Design-Kit |
| [07 Registry und Apps](07-registry-und-apps.md) | Manifeste, Prüfung, Status, Menü, Quelle austauschen |
| [08 C4 Container](08-c4-container.md) | C4-Modell Level 2 (Mermaid): Backend, Redis, Dateien, IdP |

## Schnellstart

```sh
make setup        # uv sync
make dev          # Testpersonen-Login, http://127.0.0.1:8000
make server-up    # Redis + Keycloak + Backend im Container, http://localhost:8000
make test
```

## Bekannte Lücken

- Registry liest `dev/manifests/*.json` (statt SQLite), Status kommt aus `dev/state.yml` (statt Prober).
- `/apps/<slug>/` ist eine Platzhalter-Seite; Traefik-Routing, `/auth/verify` und Identity-Assertion fehlen.
- Kein Rate-Limit auf `/login`, kein `revoke-sessions` (02 §4, §9).
- Keine Prod-Konfiguration (siehe [04 Anmeldung](04-anmeldung.md#umstieg-auf-prod)).
- Keycloak-Compose ohne Healthcheck; das Backend wartet nicht auf Redis.
- Das gehärtete `Dockerfile` (dhi.io) braucht Login und ist nicht in CI/Compose eingebunden.

## API-Dokumentation

Die Referenz zu Modulen, Klassen und Funktionen entsteht aus den Docstrings: `make docs`, danach
`open docs/api/_build/html/index.html`. Siehe [02 Entwicklung](02-entwicklung.md#api-dokumentation-sphinx).

## Pflege

Kapitel beschreiben, **wie es jetzt ist** – keine Historie, keine Begründungen von Entscheidungen. Ändert sich
Verhalten, Struktur oder ein Befehl, wird das Kapitel im selben Zug angepasst.
