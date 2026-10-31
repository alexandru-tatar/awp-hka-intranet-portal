# Portal-SDK

Die einzige Stelle in einer App, die die angemeldete Person liest, den Seitenrahmen baut und andere Systeme aufruft. Spezifikation: `claude-proposal/06-portal-sdk.md`.

```text
sdk/
├── python/platform_sdk/     Quellcode (Python, FastAPI)
├── python/tests/            Tests des SDK (pytest)
├── javascript/platform_sdk/ Quellcode (JavaScript, Express, Nunjucks)
├── javascript/tests/        Tests des SDK (node:test)
├── tools/release.py         baut die auslieferbaren Kopien und trägt die Prüfsummen ein
├── sdk-releases.json        freigegebene Versionen mit Prüfsumme je Sprache (Pipeline: PF-103)
└── dist/                    gebaute Kopien (nicht in Git)
```

Beide Fassungen haben dieselbe Version, dieselben Namen und dasselbe Verfahren für die Prüfsumme. Die Namen in JavaScript: `Portal.fromEnv`, `portal.install(app)`, `portal.router()`, `portal.requires(...)`, `req.portal.user`, `portal.url`, `portal.layout`, `portal.adapters.noten.listMyGrades(req)` und `AdapterError` (mit `detail` und `requestId`).

## Befehle (im Portal-Repository)

| Befehl | Was passiert |
|---|---|
| `make sdk-test` | Tests des SDK (Python und JavaScript; die JavaScript-Tests brauchen Node 24 oder neuer) |
| `make sdk-release` | `sdk/dist/python/platform_sdk/` und `sdk/dist/javascript/platform_sdk/` bauen (mit Design-Kit und `SHA256`), `sdk-releases.json` aktualisieren |

In einem Starter holt `make sdk-update` die gebaute Kopie nach `platform_sdk/` (Python: `sdk/dist/python/platform_sdk`, JavaScript: `sdk/dist/javascript/platform_sdk`).

## Stand

Version `1.0.0-dev`, vorläufig, in Python und JavaScript. Umgesetzt (in beiden Fassungen): Prüfung der Assertion (§5), JWKS-Zwischenspeicher (§6), Middleware mit `/healthz` (§4), `layout()` mit Ersatz-Menü, Test-Anmeldung im Entwicklungsmodus (§7), Noten-Client mit Testdaten (§8), Prüfsumme (§10), JSON-Log (§11).

Offen:

- Gemeinsamer Prüffall-Katalog `sdk-fixtures/` (F1–F22 als Dateien, §9); die Tests beider Sprachen decken die Fälle bisher mit eigenen Tokens ab. Die JavaScript-Tests enthalten F1–F9, F12, F14, F15 und F17–F22 wie die Python-Tests.
- Mail- und E-Akte-Client (in beiden Sprachen); Erzeugung der Clients aus den OpenAPI-Dateien (`tools/gen_clients.py`).
- Zwischenspeicher für das Menü mit `If-None-Match` (S7); Abruf der Schlüssel beim Start.
- `X-Portal-Kit` nennt einen Namen für CSS und JS; das Kit erzeugt getrennte Hashes (`kit-manifest.json`). Mit `04` §8 abstimmen.
- Das eigene CSS der App wird immer als `{PORTAL_BASE_PATH}/static/app.css` eingebunden (Vorschlag; im Architekturvorschlag nicht festgelegt; in beiden Sprachen gleich).
- Die Vorlagen des JavaScript-SDK sind aus der Python-Fassung übernommen und für Nunjucks angepasst (`| safe` statt `Markup`, ein `set`-Block statt eines Makros, `+` statt `~`).
