# bwSync&Share (`portal.adapters.bwsync`)

## Wozu

Dateien und Ordner im bwSync&Share-Konto (Nextcloud) **der angemeldeten Person**: auflisten, hoch- und
herunterladen, Ordner als ZIP, Ordner anlegen, verschieben/umbenennen, löschen. Andere Konten sind nicht erreichbar.
Pfade sind relativ zur Wurzel des Kontos, z. B. `"Studium/plan.pdf"`; `""` ist die Wurzel.

## Voraussetzungen

- Rechte in `manifest.json` → `adapters`: `bwsync:read` (lesen), `bwsync:write` (anlegen, hochladen, verschieben),
  `bwsync:delete` (löschen). Nur eintragen, was die App wirklich braucht.
- Die Person muss ihr Konto einmal **verbinden**. Ob das geschehen ist: `is_linked()`. Verbinden und Trennen laufen
  im Browser über das Skript `connect/connect.js` (siehe „Konto verbinden“).

## Aufrufe

Python `await portal.adapters.bwsync.<aufruf>(…)`, JavaScript `await portal.adapters.bwsync.<aufruf>(req, …)`.

| Python | JavaScript | Recht | Rückgabe, Grenzen |
|---|---|---|---|
| `is_linked()` | `isLinked(req)` | read | `bool`; ohne Kontonamen |
| `list(path="")` | `list(req, path = "")` | read | `Folder`; höchstens 1000 Einträge (`truncated`) |
| `download(path, max_bytes=10_000_000)` | `download(req, path, { maxBytes })` | read | Inhalt als Bytes; größer → `download-too-large` |
| `download_zip(path)` | `downloadZip(req, path)` | read | Strom (nicht die Wurzel); Fehler kommen beim Öffnen |
| `upload(path, data)` | `upload(req, path, data)` | write | neue Datei, höchstens 10 MB, überschreibt nie |
| `mkdir(path)` | `mkdir(req, path)` | write | neuer Ordner; Elternordner muss existieren |
| `move(source, target)` | `move(req, source, target)` | write | verschieben oder umbenennen, überschreibt nie |
| `delete(path, folder=False)` | `delete(req, path, { folder })` | delete | Datei; mit `folder` Ordner samt Inhalt (nie die Wurzel), landet im Papierkorb von bwSync&Share |

Ungültige Pfade (leer, `..`, `\ % ? # :`, Steuerzeichen, Teil > 255 oder Pfad > 1024 Zeichen) lehnt der Client vor
dem Senden ab (Python `ValueError`, JavaScript `TypeError`). Vorher prüfen mit `paths`:

| Python `paths.` | JavaScript `paths.` | Zweck |
|---|---|---|
| `MAX_NAME`, `MAX_PATH`, `FORBIDDEN_CHARS` | gleich | 255, 1024, `/\:%?#` |
| `valid_name(name)` | `validName(name)` | Name erlaubt? |
| `clean_name(raw)` | `cleanName(raw)` | letzter Teil eines Upload-Namens, ohne Steuerzeichen |
| `valid_path(path, root=True)` | `validPath(path, { root })` | Pfad erlaubt? `""` nur mit `root` |
| `join`, `parent_of`, `name_of` | `join`, `parentOf`, `nameOf` | Pfade zusammensetzen und zerlegen |
| `breadcrumbs(path)` | `breadcrumbs(path)` | `[{name, path}]` für eine Pfadleiste (ohne Wurzel) |

## Daten

`Folder`: `path` (str), `entries` (Liste `FolderEntry`, Ordner zuerst, dann nach Namen), `truncated` (bool: mehr
als 1000 Einträge, nur die ersten), `skipped` (int: Namen, die der Adapter nicht verarbeiten kann, fehlen).

`FolderEntry`: `name` (1–255 Zeichen, ohne `/`), `type` (`"folder"` oder `"file"`), `size` (Bytes; bei Ordnern
`None`/`null`), `modified` (Zeitpunkt mit Zeitzone oder `None`/`null`). Anzeigen mit `common.sizes` und
`common.dates`.

## Fehler

Alle Fehler sind `AdapterError`. Entscheiden nach `type` (Konstante aus `errors` bzw. `transport`), Text schreibt die
App. Einteilung und Standardbehandlung nicht abgefangener Fehler: `sdk/README.md`, Abschnitt „Fehler: Standard“.

Fachlich (bwSync&Share):

| `type` (Konstante) | `status` | Bedeutung | empfohlene Reaktion |
|---|---|---|---|
| `bwsync-not-linked` (`NOT_LINKED`) | 403 | Konto nicht verbunden | „Verbinden“ anbieten |
| `bwsync-link-invalid` (`LINK_INVALID`) | 403 | Verbindung gilt nicht mehr (App-Passwort widerrufen oder gespeicherter Zugang nicht mehr lesbar) | neu verbinden anbieten |
| `bwsync-link-failed` (`LINK_FAILED`) | 403 | nur beim Verbinden (über `connect.js`): bwSync&Share lehnt den gerade erhaltenen Zugang ab | erneut verbinden; wenn es wieder passiert, Support |
| `bwsync-forbidden` (`FORBIDDEN`) | 403 | bwSync&Share verweigert die Aktion (z. B. nur lesbar geteilt) | sagen, dass es hier nicht geht |
| `bwsync-not-found` (`NOT_FOUND`) | 404 | Datei oder Ordner gibt es nicht (mehr) | sagen, dass es das nicht mehr gibt; Liste neu laden |
| `bwsync-exists` (`EXISTS`) | 409, 412 | Name gibt es dort schon | anderen Namen erbitten |
| `bwsync-parent-missing` (`PARENT_MISSING`) | 409 | Zielordner fehlt | sagen, dass der Ordner fehlt; Liste neu laden |
| `bwsync-conflict` (`CONFLICT`) | 409 | sonstiger Konflikt, z. B. Ordner als Datei gelöscht | sagen, dass es gerade nicht geht; Seite neu laden und erneut versuchen |
| `bwsync-too-large` (`TOO_LARGE`) | 413 | Upload über 10 MB | Grenze nennen (10 MB) |
| `bwsync-locked` (`LOCKED`) | 423 | in bwSync&Share gesperrt (z. B. geöffnet) | sagen, dass die Datei gesperrt ist; später erneut |
| `bwsync-not-a-file` (`NOT_A_FILE`) | 409 | Datei erwartet, es ist ein Ordner (z. B. Datei löschen) | sagen, dass es ein Ordner ist; Liste neu laden |
| `bwsync-not-a-folder` (`NOT_A_FOLDER`) | 409 | Ordner erwartet, es ist eine Datei (auflisten, Ordner löschen) | sagen, dass es eine Datei ist; Liste neu laden |
| `bwsync-move-into-self` (`MOVE_INTO_SELF`) | 400 | Ziel ist die Quelle selbst oder ein Ordner in ihr | anderen Zielordner wählen lassen |
| `bwsync-folder-too-large` (`FOLDER_TOO_LARGE`) | 422 | Ordnerliste größer als die Grenze des Adapters | sagen, dass der Ordner zu groß ist; direkt in bwSync&Share öffnen |

Allgemein (Konstanten in `transport`):

| `type` (Konstante) | `status` | Bedeutung | empfohlene Reaktion |
|---|---|---|---|
| `backend-unavailable` (`transport.BACKEND_UNAVAILABLE`) | 503 u. a. | Adapter nicht erreichbar, abgestürzt oder Antwort ohne eigenen `type` | später erneut. Kommt er bei normaler Bedienung, fehlt im Adapter ein `type`: als Fehler im Adapter melden |
| `backend-timeout` (`transport.BACKEND_TIMEOUT`) | 504 | Adapter oder bwSync&Share zu langsam | später erneut |
| `contract-violation` (`transport.CONTRACT_VIOLATION`) | 502 | Antwort passt nicht zur Beschreibung | später erneut, Log prüfen |
| `download-too-large` (`transport.DOWNLOAD_TOO_LARGE`) | 413 | größer als `max_bytes` der App | Grenze nennen |
| `not-implemented` (`transport.NOT_IMPLEMENTED`) | 501 | `make dev` ohne Adapter: bwSync gibt es dort nicht | Gateway-Testbetrieb nutzen |
| `no-user-context` (`transport.NO_USER_CONTEXT`) | 500 | Aufruf außerhalb einer Anfrage einer angemeldeten Person | Programmierfehler beheben |
| `scope-not-granted` (`transport.SCOPE_NOT_GRANTED`) | 403 | der App fehlt das Recht (z. B. `bwsync:delete`) im Manifest | Programmierfehler: Recht im Manifest ergänzen |

`errors.LINK_PROBLEMS` enthält `NOT_LINKED` und `LINK_INVALID` (in beiden Fällen: verbinden anbieten).

## Konto verbinden

`connect/connect.js` (in Python und JavaScript byte-gleich) spricht nur mit dem Gateway (`connect.ROUTES`) und hat
keine Oberfläche und keine Texte. `portal.install(app)` liefert es unter `<app>/_sdk/bwsync/connect.js` aus (nur für
angemeldete Personen); die Adresse ist `portal.url(connect.SCRIPT)`. Die App bindet es vor ihrem eigenen Skript ein
(`<script src="…" defer>`) und baut Knopf, Texte und Dialog selbst.

Im Browser steht danach `window.PortalBwSync` bereit:

| Aufruf | Ergebnis |
|---|---|
| `connect(onState)` | direkt im Klick aufrufen (sonst blockiert der Browser den neuen Tab). `onState` bekommt `{state: "waiting"}`, dann `{state: "linked", account}` oder `{state: "error", type, status}`. Rückgabe `{cancel()}` |
| `disconnect()` | Promise `{linked: false, revoked}`: `true` App-Passwort widerrufen, `null` nicht vom Portal angelegt (bleibt), `false` Widerruf nicht bestätigt oder nicht möglich (Zugang nicht mehr lesbar) |
| `status()` | Promise `{linked, account}` |

Fehler kommen als `{type, status}` (bei `disconnect`/`status` als abgelehnte Promise). Neben den Typen aus der
Tabelle oben meldet das Skript selbst (Konstanten in `connect` und `window.PortalBwSync.ERRORS`):

| `type` (Konstante) | Bedeutung | empfohlene Reaktion |
|---|---|---|
| `connect-popup-blocked` (`POPUP_BLOCKED`) | Browser hat den neuen Tab blockiert | Pop-ups erlauben lassen |
| `connect-expired` (`EXPIRED`) | Anmeldung nicht rechtzeitig abgeschlossen | erneut verbinden |
| `connect-aborted` (`ABORTED`) | Anmeldung abgebrochen | erneut verbinden |
| `portal-session-expired` (`SESSION_EXPIRED`) | Sitzung im Portal abgelaufen (401) | Seite neu laden |
| `backend-unavailable` | Gateway oder Adapter nicht erreichbar | später erneut |

```js
// im Skript der App (Texte schreibt die App)
button.addEventListener("click", () => {
  window.PortalBwSync.connect((s) => {
    if (s.state === "waiting") status.textContent = "Bitte im neuen Tab anmelden …";
    if (s.state === "linked") window.location.reload();
    if (s.state === "error") status.textContent = TEXTE[s.type] || "Das hat nicht geklappt.";
  });
});
```

## Tests

`testing.FakeBwSync` ist ein Konto im Speicher mit denselben Fehlertypen wie der Adapter. `install(portal)` setzt
`portal.adapters.bwsync` auf den Fake, `uninstall()` stellt zurück. Felder: `folders`, `files`, `calls`
(`(methode, pfad, body)`), `fail = (status, type)`, `linked`, `listing` (feste Antwort für `list`), `streams`.
`add_file(path, data)` legt eine Datei samt Elternordnern an. Aufrufe außerhalb einer Anfrage scheitern wie im
Betrieb mit `no-user-context`.

```python
from platform_sdk.adapters.bwsync.testing import FakeBwSync

@pytest.fixture
def bwsync():
    fake = FakeBwSync().install(portal)
    yield fake
    fake.uninstall()
```

```js
const { FakeBwSync } = require("../platform_sdk/adapters/bwsync/testing");
const bwsync = new FakeBwSync().install(portal); // nach dem Test: bwsync.uninstall()
```

## Beispiele

Ordner anzeigen (Python):

```python
from platform_sdk import AdapterError
from platform_sdk.adapters.bwsync import errors, paths

try:
    folder = await portal.adapters.bwsync.list(pfad)
except AdapterError as err:
    if err.type in errors.LINK_PROBLEMS:
        return render("verbinden.html")
    raise
crumbs = paths.breadcrumbs(pfad)
```

Ordner anlegen (JavaScript):

```js
const { AdapterError } = require("../platform_sdk");
const { errors, paths } = require("../platform_sdk/adapters/bwsync");

if (!paths.validName(name)) return res.status(400).render("seite.html", { fehler: "Ungültiger Name." });
try {
  await portal.adapters.bwsync.mkdir(req, paths.join(pfad, name));
} catch (err) {
  if (err instanceof AdapterError && err.type === errors.EXISTS) {
    return res.status(409).render("seite.html", { fehler: "Diesen Namen gibt es hier schon." });
  }
  throw err;
}
```

Ordner als ZIP (Python):

```python
from platform_sdk.common.downloads import download_headers

stream = await portal.adapters.bwsync.download_zip(pfad)  # Fehler hier, bevor geantwortet wird
return StreamingResponse(stream, media_type="application/zip",
                         headers=download_headers(paths.name_of(pfad) + ".zip"),
                         background=BackgroundTask(stream.aclose))
```
