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
   der App. Vom Portal vorgegeben und deshalb im SDK: Seitenrahmen (`layout`), Fehlerseite (auch für die
   Standardbehandlung von Fehlern, siehe „Fehler: Standard“), Test-Anmeldung.
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
   `backend-timeout`, `contract-violation`, `not-implemented`, `download-too-large`, `no-user-context`,
   `scope-not-granted`.
   - Einteilung in fachlich, technisch und Aufruf, Standardbehandlung und Regeln für neue Typen: Abschnitt
     „Fehler: Standard“ unten.
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

## Fehler: Standard

> **Kurz:** Fachliche Fehler (von einer Person bei normaler Bedienung ausgelöst) bekommen im Adapter immer einen
> eigenen `type` mit 4xx, als Konstante im SDK. Technische Fehler und Aufruffehler fängt das SDK mit allgemeinen
> Typen ab; den Text für die Person schreibt immer die App.

Dass kein fachlicher Fall ohne `type` endet, soll ein gemeinsamer Vertragstest im Adapter prüfen (Jira HKA-78): Jedes
Fachsystem liefert nur seine Liste von Fällen, der Prüfteil ist für alle gleich.

### Drei Arten

| Art | Wer legt den `type` fest | Konstante in | Beispiele | Reaktion der App |
|---|---|---|---|---|
| **Fachlich:** ein System lehnt eine Aktion ab oder kennt etwas nicht | nur der **Adapter** | `adapters/<system>/errors` | `bwsync-not-found`, `bwsync-locked`, `bwsync-link-invalid` | eigener Text je `type`, nächster Schritt für die Person |
| **Technisch:** kann bei jedem System passieren | nur das **SDK** | `adapters/transport` (`TECHNICAL_TYPES`) | `backend-unavailable`, `backend-timeout`, `contract-violation` | ein gemeinsamer Text: später erneut versuchen |
| **Aufruf:** die App hat eine Grenze oder Regel des SDK verletzt | das **SDK** (Ausnahme siehe unten) | `adapters/transport` (`CALL_TYPES`) | `download-too-large`, `no-user-context`, `not-implemented`, `scope-not-granted` | Grenze nennen bzw. Programmierfehler beheben |

- Aufruf-Typen legt das SDK fest, außer Plattform-Prüfungen im Adapter wie `scope-not-granted` (403: der App fehlt
  das Recht im Manifest).
- Ein fachlicher Fall hat **immer** einen eigenen `type` mit passendem 4xx-Status, nie 500 oder 502 ohne `type`.
  Fehlt der `type`, ist das ein Fehler im Adapter, nicht in der App.
- `backend-unavailable` heißt nur: keine verwertbare Antwort (Netz weg, Absturz, Antwort ohne `type`). Kommt er bei
  normaler Bedienung, gehört ein `type` in den Adapter.
- Jeder `type`, der nicht in `TECHNICAL_TYPES` oder `CALL_TYPES` steht, ist fachlich. `transport.category(err)` gibt
  `"domain"`, `"technical"` oder `"call"` zurück.
- Fakes in `testing` melden dieselben Typen wie der Adapter, als Konstante, nie als getippten Text.
- Den Text für die Person schreibt die App (R-SCHN-3). `detail` ist für Logs.

### Standardbehandlung (Fallback)

Fängt die App einen Fehler nicht selbst ab, antwortet das SDK mit seiner Fehlerseite (Browser: HTML, sonst
problem+json). Python: richtet `portal.install(app)` ein. JavaScript: `portal.handleErrors(app)` als **letzte** Zeile,
nach allen Routen (Express ruft Fehler-Handler nur nach den Routen auf).

| Fehler | Status | Titel und Text der Seite | Log |
|---|---|---|---|
| `AdapterError`, fachlich | Status vom Adapter (4xx) | „Das hat nicht geklappt“ – Die Aktion war nicht möglich. Bitte gehen Sie zurück, laden Sie die Seite neu und versuchen Sie es erneut. | WARN: `type`, `status`, Vorgangsnummer; die App behandelt diesen `type` nicht |
| `AdapterError`, technisch | 503 (`backend-timeout`: 504) | „Gerade nicht erreichbar“ – Der Dienst ist gerade nicht erreichbar. Bitte versuchen Sie es später erneut. | WARN: `type`, `status`, Vorgangsnummer |
| `AdapterError`, Aufruf | 500 | „Fehler in der Anwendung“ – In dieser Anwendung ist ein Fehler aufgetreten. Wenn das wieder passiert, nennen Sie bitte die Vorgangsnummer. | ERROR: `type`, `status`, `detail`, Vorgangsnummer |
| jeder andere Fehler | 500 | wie „Aufruf“ | ERROR mit Stack, Vorgangsnummer |

- Die Seite zeigt immer die Vorgangsnummer. `detail`, Traceback und Stack stehen nie in der Antwort, nur im Log.
- problem+json trägt bei einem `AdapterError` den ursprünglichen `type` (z. B. `urn:hka:problem:bwsync-locked`),
  sonst `urn:hka:problem:<status>`. So kann das Skript der App weiter nach `type` entscheiden.
- Fängt die App den Fehler selbst ab, greift der Fallback nicht. Jeder Fall lässt sich so überschreiben.
- Der Fallback ist ein **Sicherheitsnetz, kein Ersatz**: Jeder `type`, bei dem die Person etwas anderes tun soll,
  bekommt in der App einen eigenen Text (Spalte „empfohlene Reaktion“ im README des Systems).
- Die Texte stehen auf der Fehlerseite des SDK; das ist die Ausnahme aus Regel 1.
- Grenze: Kommt ein Fehler erst, nachdem die Antwort begonnen hat (z. B. mitten in einem ZIP-Strom), bricht die
  Antwort ab; eine Seite lässt sich dann nicht mehr zeigen.

### Wann ein neuer Typ ins SDK kommt

Nur wenn **alle drei** Punkte zutreffen:

1. Eine Person kann den Fall bei normaler Bedienung auslösen.
2. Eine App soll darauf anders reagieren als auf vorhandene Typen (anderer nächster Schritt, nicht nur anderer
   Wortlaut).
3. Der Adapter erkennt den Fall sicher.

Kein neuer Typ für technische Ursachen (dafür gibt es die allgemeinen), für Einzelheiten aus dem Fachsystem (die
gehören in `detail` bzw. ins Log) und für Prüfungen, die nur eine App braucht (die bleiben in der App).

Name: `<system>-<fall>`, klein mit Bindestrich, gesendet als `urn:hka:problem:<name>`. Ein Typ wird nie umbenannt und
bekommt nie eine neue Bedeutung, ohne dass die SDK-Version steigt.

### Was ins SDK kommt

Nur, was **jede** App braucht, die das System nutzt: Aufrufe, Modelle, Fehlertypen, Regeln, die der Adapter
durchsetzt (z. B. `paths`), Fake, `connect`. Logik, Texte und HTML einer einzelnen App bleiben in der App. Beispiel:
Die Verschieben-Prüfung und der Satz zum Ordnerinhalt von SyncShare stehen in SyncShare, nicht im SDK.

### Neuen Typ hinzufügen

- [ ] **Adapter:** Konstante anlegen, `ConnectorError(status, detail, kind)` werfen; Test, der Status **und** `type`
      prüft; Fall in die Liste des Vertragstests (HKA-78); Fehlerliste in der Adapter-README.
- [ ] **SDK, beide Sprachen:** Konstante in `adapters/<system>/errors`; der Fake wirft denselben Typ; Zeile in der
      Fehler-Tabelle der System-README (`type`, `status`, Bedeutung, empfohlene Reaktion); Paritätstest grün;
      Version erhöhen, `make sdk-release`.
- [ ] **Golden Master und Apps:** `make sdk-update`; die App behandelt den Typ mit eigenem Text; Test mit
      `Fake…(fail=(status, errors.NEU))`.

## README eines Systems

Jede `adapters/<system>/README.md` hat dieselben Abschnitte:

1. **Wozu:** was das System ist, wessen Daten (immer nur die der angemeldeten Person).
2. **Voraussetzungen:** Rechte im `manifest.json` (z. B. `bwsync:read`), ggf. Konto verbinden.
3. **Aufrufe:** jede Funktion mit Parametern, Rückgabe, nötigem Recht und Grenzen.
4. **Daten:** jedes Feld der Modelle mit Typ und Bedeutung.
5. **Fehler:** Tabelle `type` · `status` · Bedeutung · empfohlene Reaktion, getrennt nach fachlichen Typen des
   Systems und allgemeinen Typen.
6. **Tests:** wie der Fake eingesetzt wird.
7. **Beispiele:** zwei bis drei kurze, in Python und JavaScript.

## Neues System anschließen

- [ ] Adapter-Dienst ist beschrieben (OpenAPI) und läuft im lokalen Stack.
- [ ] Ordner `adapters/<system>/` in **beiden** Sprachen mit `client`, `models`, `errors`, `testing`, `README.md`;
      `connect` nur, wenn die Person ihr Konto selbst verbinden muss.
- [ ] `client`: nur Aufrufe aus der OpenAPI-Beschreibung; Pfade und Parameter geprüft, bevor gesendet wird.
- [ ] `models`: streng, nur Felder aus der Beschreibung.
- [ ] `errors`: alle `type`, die der Adapter liefern kann, als Konstanten; Bedeutung und Reaktion in der README;
      jeder fachliche Fall hat einen `type` (siehe „Fehler: Standard“).
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
Aktuell: `1.2.0-dev`.
