# Portal-SDK

Bibliothek für Apps im HKA-Portal, in Python (FastAPI) und JavaScript (Express). Sie liest die angemeldete Person,
baut den Seitenrahmen und ist der **einzige Weg zu anderen Systemen**. Für jedes System beschreibt sie genau, welche
Aufrufe, Felder und Fehler es gibt, damit beim Bauen einer App (auch mit KI) nichts erfunden wird.

## Aufbau

```text
sdk/
├── python/platform_sdk/       Quellcode Python
├── python/tests/
├── javascript/platform_sdk/   Quellcode JavaScript
├── javascript/tests/
├── tools/release.py           baut die Kopien für die Apps und trägt die Prüfsummen ein
├── sdk-releases.json          freigegebene Versionen mit Prüfsumme je Sprache
└── dist/                      gebaute Kopien für die Apps; nicht in Git (.gitignore), entsteht mit make sdk-release
```

In beiden Sprachen gleich:

```text
platform_sdk/
├── portal, layout, middleware, verify, jwks, config, context, errors, pages, devshim
├── adapters/
│   ├── __init__            portal.adapters.<system>
│   ├── transport           HTTP zum Adapter-Dienst; im Entwicklungsmodus feste Testdaten
│   └── <system>/           ein Ordner je System, z. B. bwsync/, noten/
│       ├── client          alle Aufrufe des Systems
│       ├── models          Datenmodelle der Antworten (streng: unbekannte Felder sind ein Fehler)
│       ├── errors          Fehlertypen als Konstanten (Bedeutung höchstens als Kommentar)
│       ├── testing         Fake des Systems für Tests der App
│       ├── connect/        nur wenn die Person ihr Konto verbinden muss:
│       │   ├── server      Routen des Gateways und Adresse des Skripts (ob verbunden: client)
│       │   └── connect.js  Browser-Skript ohne Oberfläche (Verbinden, Trennen)
│       ├── …               weitere nur wenn nötig, z. B. paths (Regeln für Pfade)
│       └── README.md       Beschreibung der Schnittstelle (siehe unten)
├── common/
│   ├── dates               Zeitpunkte in Europe/Berlin, deutsches Format
│   ├── sizes               Dateigrößen lesbar („1,2 MB“)
│   └── downloads           Content-Disposition, Schutz-Header für Downloads
└── VERSION, SHA256
```

Das Browser-Skript liegt in `adapters/<system>/connect/connect.js`, ist in Python und JavaScript byte-gleich, und
`portal.install(app)` liefert es unter `<app>/_sdk/<system>/connect.js` aus. Die App gibt die Adresse
`portal.url("/_sdk/<system>/connect.js")` an ihre Vorlage, bindet sie dort mit `<script src="…" defer>` ein und baut
Knopf, Texte und Dialog selbst; das Skript meldet nur Zustände (wartet, verbunden, Fehler mit `type`).

## Regeln

1. **Reine Bibliothek.** Unter `adapters/` und `common/` gibt es kein HTML, kein CSS, keine Vorlagen und keine
   Texte für Nutzer. Oberfläche, Wortwahl und Muster dafür stehen im Golden Master (Skill `schnittstellen`) oder in
   der App. Vom Portal vorgegeben und deshalb im SDK: Seitenrahmen (`layout`), Fehlerseite, Test-Anmeldung.
2. **Andere Systeme nur über das SDK.** Eine App ruft nie selbst einen Dienst auf, sondern
   `portal.adapters.<system>.<aufruf>(…)`. Das SDK schickt die Anmeldung der Person mit; die App braucht kein
   Passwort und kein Token. Durchgesetzt durch Regel R-SCHN-1 im Golden Master: `make lint` meldet eigene
   Netzaufrufe (Python: Ruff verbietet u. a. `requests`, `httpx`, `urllib.request`, `socket`; JavaScript: ESLint
   verbietet u. a. `fetch`, `axios`, `node:http`), der Starter-Selbsttest (`make check`) prüft, dass diese Verbote
   vollständig sind und für `src/` nicht abgeschaltet werden, und im Betrieb hat die App kein Internet.
3. **Nur, was beschrieben ist.** Was nicht in der README des Systems steht, gibt es nicht.
4. **Fehler sind `AdapterError`.** Felder: `status` (HTTP-Status), `type` (z. B. `bwsync-exists`), `detail`,
   `request_id`. Jeder `type` steht als Konstante in `adapters/<system>/errors`; Bedeutung und typische Reaktion stehen
   in der Fehler-Tabelle der README des Systems. Allgemeine Typen (Konstanten in `adapters/transport`): `backend-unavailable`,
   `backend-timeout`, `contract-violation`, `not-implemented`, `download-too-large`, `no-user-context`.
   - Die App entscheidet **immer anhand von `type`** (und `status`), nie anhand eines Textes, und vergleicht mit der
     Konstante, nie mit einem selbst getippten String.
   - Den **Text für die Person schreibt die App** selbst.
   - `detail` ist für Logs und Fehlersuche (Text des Adapters, Sprache beliebig; leer, wenn keine Antwort vom Adapter
     kam). Die App darf ihn zusätzlich anzeigen, wenn er passt, muss aber nicht.
5. **Aufrufe nur innerhalb einer Anfrage** einer angemeldeten Person (dort kennt das SDK die Person).
6. **Python und JavaScript sind gleich:** dieselben Ordner, Dateien, Funktionen und Fehlertypen. Namen in Python
   `snake_case`, in JavaScript `camelCase`; JavaScript-Aufrufe bekommen zuerst `req`.

   | Python | JavaScript |
   |---|---|
   | `await portal.adapters.bwsync.list(pfad)` | `await portal.adapters.bwsync.list(req, pfad)` |
   | `except AdapterError as err:` | `catch (err) { if (err instanceof AdapterError) … }` |
   | `err.type == errors.EXISTS` | `err.type === errors.EXISTS` |
   | `from platform_sdk.adapters.bwsync.testing import FakeBwSync` | `const { FakeBwSync } = require("../platform_sdk/adapters/bwsync/testing")` |

7. **Unverändert in der App.** Apps bekommen eine Kopie in `platform_sdk/` und ändern sie nicht; `verify_tree`
   prüft die Prüfsumme gegen `sdk-releases.json`.

## README eines Systems

Jede `adapters/<system>/README.md` hat dieselben Abschnitte:

1. **Wozu:** was das System ist, wessen Daten (immer nur die der angemeldeten Person).
2. **Voraussetzungen:** Rechte im `manifest.json` (z. B. `bwsync:read`), ggf. Konto verbinden.
3. **Aufrufe:** jede Funktion mit Parametern, Rückgabe, nötigem Recht und Grenzen.
4. **Daten:** jedes Feld der Modelle mit Typ und Bedeutung.
5. **Fehler:** Tabelle `type` · `status` · Bedeutung · empfohlene Reaktion.
6. **Tests:** wie der Fake eingesetzt wird.
7. **Beispiele:** zwei bis drei kurze, in Python und JavaScript.

## Neues System anschließen

- [ ] Adapter-Dienst ist beschrieben (OpenAPI) und läuft im lokalen Stack.
- [ ] Ordner `adapters/<system>/` in **beiden** Sprachen mit `client`, `models`, `errors`, `testing`, `README.md`;
      `connect` nur, wenn die Person ihr Konto selbst verbinden muss.
- [ ] `client`: nur Aufrufe aus der OpenAPI-Beschreibung; Pfade und Parameter geprüft, bevor gesendet wird.
- [ ] `models`: streng, nur Felder aus der Beschreibung.
- [ ] `errors`: alle `type`, die der Adapter liefern kann, als Konstanten; Bedeutung und Reaktion in der README.
- [ ] `testing`: Fake, der sich wie der Adapter verhält (gleiche Fehler); dazu feste Testdaten für `make dev`.
- [ ] `adapters/__init__`: `portal.adapters.<system>` eintragen.
- [ ] Rechte (`<system>:read` usw.) im Portal (`adapter_scopes`) und im Manifest-Schema.
- [ ] Tests in beiden Sprachen, dazu ein Test, dass beide dieselben Funktionen und Fehlertypen haben.
- [ ] README nach dem Schema oben; Skill `schnittstellen` im Golden Master verweist darauf.
- [ ] `make sdk-test`, Version erhöhen, `make sdk-release`, in den Golden Mastern `make sdk-update`.

## Befehle (im Portal-Repository)

| Befehl | Was passiert |
|---|---|
| `make sdk-test` | Tests des SDK in Python und JavaScript (JavaScript braucht Node 24 oder neuer) |
| `make sdk-release` | Kopien nach `sdk/dist/<sprache>/platform_sdk/` bauen (mit Design-Kit und `SHA256`), `sdk-releases.json` aktualisieren |

In einer App holt `make sdk-update SDK_DIST=<Portal-Repository>/sdk/dist/<sprache>/platform_sdk` die neue Kopie.

## Version

Eine Version für beide Sprachen, in `python/platform_sdk/VERSION`, `javascript/platform_sdk/VERSION` und
`javascript/package.json`. Jede Änderung unter `platform_sdk/` braucht eine neue Version und `make sdk-release`.
Aktuell: `1.1.0-dev`.
