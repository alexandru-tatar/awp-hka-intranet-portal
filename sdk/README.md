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

Python unterstützt zusätzlich `portal.adapters.bwsync.upload(path, data)` und
`download(path, max_bytes=...)` für den lokalen bwSync-Test, ab `1.0.3-dev` auch den
Datei-Explorer: `list(path="")` (gibt `Folder` mit `entries`, `truncated`, `skipped`),
`mkdir(path)`, `move(src, dst)` (nie überschreiben) und `delete(path, folder=False)`
(nur leere Ordner), ab `1.0.5-dev` `download_zip(path)`: Ordner als ZIP, gestreamt (`AdapterStream`
für `StreamingResponse`, Fehler schon beim Öffnen; nicht die Wurzel). Scopes im Manifest: `bwsync:read`, `bwsync:write`, für Löschen
eigens `bwsync:delete`. Fehler kommen als `AdapterError` mit `type`, z. B.
`bwsync-not-linked`, `bwsync-exists`, `bwsync-parent-missing`, `bwsync-folder-not-empty`. Der HTTP-Transport
verlangt die vorhandene App-Assertion, sendet rohe Bytes per PUT, akzeptiert 204
ohne JSON und begrenzt binäre Downloads. Kein bwSync-Fixture oder Auth-Bypass;
die JavaScript-Fassung hat diesen Client noch nicht. SDK-Aufrufe erfolgen innerhalb
eines authentifizierten Requests. Der derzeitige Adapter ist nur für kontrollierte
lokale Tests vorgesehen und prüft die mitgesendete Assertion noch nicht.

Version `1.0.4-dev` (Abmelden im Seitenrahmen per Dialog direkt mit POST /logout statt Link auf die Gateway-Zwischenseite; `1.0.3-dev`: bwSync-Explorer nur in Python; `1.0.2-dev` holte das Menü mit `Authorization: Bearer`, 02 §3; `1.0.0-dev` schickte `X-Portal-Assertion`), vorläufig, in Python und JavaScript. Umgesetzt (in beiden Fassungen): Prüfung der Assertion (§5), JWKS-Zwischenspeicher (§6), Middleware mit `/healthz` (§4), `layout()` mit Ersatz-Menü, Test-Anmeldung im Entwicklungsmodus (§7), Noten-Client mit Testdaten (§8), Prüfsumme (§10), JSON-Log (§11).

Offen:

- Gemeinsamer Prüffall-Katalog `sdk-fixtures/` (F1–F22 als Dateien, §9); die Tests beider Sprachen decken die Fälle bisher mit eigenen Tokens ab. Die JavaScript-Tests enthalten F1–F9, F12, F14, F15 und F17–F22 wie die Python-Tests.
- Mail- und E-Akte-Client (in beiden Sprachen); Erzeugung der Clients aus den OpenAPI-Dateien (`tools/gen_clients.py`).
- Zwischenspeicher für das Menü mit `If-None-Match` (S7); Abruf der Schlüssel beim Start.
- `X-Portal-Kit` nennt einen Namen für CSS und JS; das Kit erzeugt getrennte Hashes (`kit-manifest.json`). Mit `04` §8 abstimmen.
- Das eigene CSS der App wird immer als `{PORTAL_BASE_PATH}/static/app.css` eingebunden (Vorschlag; im Architekturvorschlag nicht festgelegt; in beiden Sprachen gleich).
- Die Vorlagen des JavaScript-SDK sind aus der Python-Fassung übernommen und für Nunjucks angepasst (`| safe` statt `Markup`, ein `set`-Block statt eines Makros, `+` statt `~`).
