# 07 – Registry und Apps

Das Portal kennt Apps über **Manifeste**. Die Registry (`src/portal/registry/`) liest sie, prüft sie und hält einen unveränderlichen
Snapshot, aus dem das Menü und die Zugriffsentscheidung entstehen. Vorgabe: `claude-proposal/03-registry.md`.

## Eine App hinzufügen

Datei `dev/manifests/<slug>.json` anlegen; im Dev-Modus wird der Ordner bei jeder Anfrage auf Änderungen geprüft
(`Registry.refresh()` in der Middleware), ein Neustart ist nicht nötig.

```json
{
  "slug": "noten",
  "name": "Meine Noten",
  "category": "Studium",
  "menu": { "label": "Meine Noten", "icon": "grades" },
  "roles": ["student"],
  "adapters": ["noten:read"],
  "claims": [],
  "version": "1.0.0"
}
```

| Feld | Pflicht | Regel |
|---|---|---|
| `slug` | ja | `^[a-z][a-z0-9-]{2,30}$`, nicht in der Liste reservierter Slugs (`RESERVED_SLUGS`, z. B. `admin`, `api`, `login`, `apps`) |
| `name` | ja | 1–60 Zeichen, keine Steuerzeichen |
| `category` | ja | `Studium`, `Verwaltung`, `Kommunikation` oder `Sonstiges` |
| `menu.label` | ja | 1–40 Zeichen |
| `menu.icon` | ja | `grades`, `mail`, `calendar`, `document`, `people`, `book`, `room`, `settings` oder `info` |
| `roles` | ja | mindestens eine Rolle aus `role_vocabulary` der Konfiguration |
| `adapters` | nein | Scopes der Form `name:aktion`, aus `adapter_scopes` der Konfiguration |
| `claims` | nein | derzeit nur `email` |
| `version` | ja | `MAJOR.MINOR.PATCH` |

Unbekannte Felder sind ein Fehler. Die Datei `schemas/manifest.schema.json` ist die Quelle; neue Felder zuerst dort eintragen.

## Prüfung (`registry/validation.py`)

`ManifestValidator.problems()` liefert alle Probleme als `<json-pointer>: <meldung>`. Erst das JSON-Schema, danach die Regeln, die das
Schema nicht ausdrückt: reservierter Slug, unbekannte Rolle, unbekannter Adapter-Scope. Ungültige oder doppelte Manifeste werden mit
`manifest_rejected file=… reason=…` ins Log geschrieben und übersprungen; die übrigen Apps bleiben verfügbar. Der Dateiname ist egal,
es zählt der `slug` im Manifest.

## Status

`dev/state.yml` ersetzt den Prober (03 §7). Apps ohne Eintrag sind `healthy`.

```yaml
noten:        { status: healthy,   last_probe_at: "2026-10-26 09:14:02", last_deployed_at: "2026-10-20 16:03" }
raumbuchung:  { status: unhealthy, last_probe_at: "…",                   last_deployed_at: "…" }
```

| Status | Menü | `/apps/<slug>/` |
|---|---|---|
| `healthy` | ja, für passende Rollen | erreichbar |
| `unhealthy` | nein | 503 (für Benutzer mit passender Rolle) |
| `registering`, `failed`, `retired` | nein | 404 |

Ein unbekannter Status wird ins Log geschrieben (`state_rejected`) und die App übersprungen.

## Menü und Zugriff

- **Menü** (`AppService.find_nav_groups`): nur gesunde Apps, die mindestens eine Rolle mit dem Benutzer teilen; Kategorien in fester
  Reihenfolge (Studium, Verwaltung, Kommunikation, Sonstiges), Einträge alphabetisch (Umlaute wie Grundbuchstaben); leere
  Kategorien entfallen.
- **Zugriff auf eine App** (`AppService.find_authorized`): Reihenfolge und Fehlerseiten siehe
  [03 Service und Router](03-service-und-router.md#zugriffsentscheidung-für-apps).
- **Statusseite** `/_portal/status`: alle Apps mit Version, Status und Zeitpunkten, nur für `platform-admin`.

## Registry-Quelle austauschen

Eine Quelle erfüllt das Protocol `RegistrySource` (`registry/sources.py`):

- `load() -> dict[str, AppView]`: alle Apps laden,
- `fingerprint() -> Hashable`: ändert sich, sobald `load()` etwas anderes liefern würde.

`ManifestDirectorySource` (Ordner mit JSON-Dateien plus `state.yml`) ist der Ersatz für die SQLite-Registry. Eine neue Quelle wird in
`context.py` (`_build_registry`) verdrahtet; Menü, Zugriff und Statusseite ändern sich dadurch nicht.

## Snapshot

`Registry` hält den aktuellen `Snapshot` (laufende Nummer plus Apps nach Slug). Leser sperren nie; `reload()` tauscht die Referenz
unter einem Lock aus (`snapshot_swapped version=… apps=…` im Log). `refresh()` lädt nur, wenn sich der `fingerprint()` geändert hat.
