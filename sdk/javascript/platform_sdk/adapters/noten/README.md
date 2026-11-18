# Noten (`portal.adapters.noten`)

## Wozu

Noten **der angemeldeten Person** aus dem Prüfungssystem, nur lesend. Fremde Noten sind nicht erreichbar.

## Voraussetzungen

- Recht in `manifest.json` → `adapters`: `noten:read`.
- Im Entwicklungsmodus (`make dev`, ohne Adapter) kommen feste Testdaten aus `fixtures/<sub>.json`; für unbekannte
  Personen eine leere Liste.

## Aufrufe

| Python | JavaScript | Recht | Rückgabe |
|---|---|---|---|
| `await portal.adapters.noten.list_my_grades(semester=None)` | `await portal.adapters.noten.listMyGrades(req, { semester })` | read | `GradeList`; mit `semester` nur dieses Semester |

## Daten

`GradeList`: `items` (Liste `Grade`, höchstens 500).

`Grade`: `module` (str, höchstens 120 Zeichen), `semester` (str, z. B. `"WS 2025/26"`), `grade` (`"1,0"` bis
`"4,0"`, `"5,0"`, `"bestanden"` oder `"nicht bestanden"`), `credits` (int 0–30 oder `None`/`null`).

## Fehler

Der Noten-Adapter hat keine eigenen Typen; es gelten die allgemeinen (Konstanten in `adapters/transport`). Einteilung und Standardbehandlung
nicht abgefangener Fehler: `sdk/README.md`, Abschnitt „Fehler: Standard“.

| `type` | `status` | Bedeutung | empfohlene Reaktion |
|---|---|---|---|
| `backend-unavailable` | 503 u. a. | Adapter nicht erreichbar, abgestürzt oder Antwort ohne eigenen `type` | später erneut |
| `backend-timeout` | 504 | Adapter zu langsam | später erneut |
| `contract-violation` | 502 | Antwort passt nicht zur Beschreibung | später erneut, Log prüfen |
| `scope-not-granted` | 403 | der App fehlt das Recht `noten:read` im Manifest | Programmierfehler: Recht im Manifest ergänzen |

## Tests

`testing.FakeNoten(grades)` mit `grades` = sub → Liste von Noten (wie `Grade`). `install(portal)`, `uninstall()`,
`calls`, `fail = (status, type)` wie bei `FakeBwSync`.

```python
from platform_sdk.adapters.noten.testing import FakeNoten

fake = FakeNoten({"test-person": [{"module": "Mathe 1", "semester": "WS 2025/26", "grade": "1,3", "credits": 5}]})
fake.install(portal)
```

```js
const { FakeNoten } = require("../platform_sdk/adapters/noten/testing");
new FakeNoten({ "test-person": [{ module: "Mathe 1", semester: "WS 2025/26", grade: "1,3", credits: 5 }] }).install(portal);
```

## Beispiele

```python
from platform_sdk import AdapterError

try:
    noten = await portal.adapters.noten.list_my_grades()
except AdapterError:
    return render("noten.html", {"fehler": "Die Noten sind gerade nicht abrufbar."})
```

```js
try {
  const noten = await portal.adapters.noten.listMyGrades(req);
  res.render("noten.html", { noten: noten.items });
} catch (err) {
  if (!(err instanceof AdapterError)) throw err;
  res.status(503).render("noten.html", { fehler: "Die Noten sind gerade nicht abrufbar." });
}
```
