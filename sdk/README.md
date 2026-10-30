# Portal-SDK

Die einzige Stelle in einer App, die die angemeldete Person liest, den Seitenrahmen baut und andere Systeme aufruft. Spezifikation: `claude-proposal/06-portal-sdk.md`.

```text
sdk/
├── python/platform_sdk/     Quellcode (Python, FastAPI)
├── python/tests/            Tests des SDK
├── tools/release.py         baut die auslieferbare Kopie und trägt die Prüfsumme ein
├── sdk-releases.json        freigegebene Versionen mit Prüfsumme (Pipeline: PF-103)
└── dist/                    gebaute Kopie (nicht in Git)
```

## Befehle (im Portal-Repository)

| Befehl | Was passiert |
|---|---|
| `make sdk-test` | Tests des SDK |
| `make sdk-release` | `sdk/dist/python/platform_sdk/` bauen (mit Design-Kit und `SHA256`), `sdk-releases.json` aktualisieren |

In einem Starter holt `make sdk-update` die gebaute Kopie nach `platform_sdk/`.

## Stand

Version `1.0.0-dev`, vorläufig. Umgesetzt: Prüfung der Assertion (§5), JWKS-Zwischenspeicher (§6), Middleware mit `/healthz` (§4), `layout()` mit Ersatz-Menü, Test-Anmeldung im Entwicklungsmodus (§7), Noten-Client mit Testdaten (§8), Prüfsumme (§10), JSON-Log (§11).

Offen:

- JavaScript-SDK und gemeinsamer Prüffall-Katalog `sdk-fixtures/` (F1–F22 als Dateien, §9); die Python-Tests decken die Fälle bisher mit eigenen Tokens ab.
- Mail- und E-Akte-Client; Erzeugung der Clients aus den OpenAPI-Dateien (`tools/gen_clients.py`).
- Zwischenspeicher für das Menü mit `If-None-Match` (S7); Abruf der Schlüssel beim Start.
- `X-Portal-Kit` nennt einen Namen für CSS und JS; das Kit erzeugt getrennte Hashes (`kit-manifest.json`). Mit `04` §8 abstimmen.
- Das eigene CSS der App wird immer als `{PORTAL_BASE_PATH}/static/app.css` eingebunden (Vorschlag; im Architekturvorschlag nicht festgelegt).
