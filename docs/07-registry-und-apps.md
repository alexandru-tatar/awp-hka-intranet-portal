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

## Weiterleitung an die App (`apps`)

Mit dem Abschnitt `apps` in der Konfiguration leitet das Portal `/apps/<slug>/…` selbst an den Container der App weiter
(`router/app_router.py`, `web/proxy.py`). Ohne den Abschnitt bleibt es bei der Platzhalter-Seite (nur `env: dev`).

```yaml
assertion:
  issuer: https://portal.example/          # muss PORTAL_ISSUER der Apps exakt entsprechen (auch der Schrägstrich am Ende)
  ttl_seconds: 60
  signing_key_current: secrets/jwt_current.pem   # PEM, RSA; ohne Datei erzeugt env dev einen flüchtigen Schlüssel
  signing_key_next: secrets/jwt_next.pem         # optional, wird nur im JWKS veröffentlicht
  signing_key_previous: secrets/jwt_previous.pem # optional, bleibt nach einem Wechsel im JWKS
apps:
  upstream: http://app-{slug}:8080         # {slug} wird ersetzt
  connect_timeout_seconds: 2
  read_timeout_seconds: 30
  max_body_bytes: 10485760
```

- **Ablauf:** Zugriffsentscheidung wie oben (`find_authorized`: 404, Anmeldung, 403, 503). Erst danach stellt das Portal das Token aus und
  leitet weiter. Eine abgewiesene Anfrage erreicht die App nie. Anfragen mit Seiteneffekt von einer fremden Seite
  (`Sec-Fetch-Site: cross-site`/`same-site` oder fremder `Origin`) beantwortet das Portal mit 403.
- **Pfad:** unverändert, also `/apps/<slug>/…` samt Query. Die App läuft mit `PORTAL_BASE_PATH=/apps/<slug>` auf Port 8080.
- **Kopfzeilen zur App:** `X-Portal-Assertion` (ersetzt jede mitgeschickte), `X-Request-Id`, `X-Forwarded-For/-Proto/-Host`.
  `Cookie` geht nie an die App, `Set-Cookie` kommt nie zurück. `Location` auf die Adresse des Containers wird zum relativen Pfad.
- **Token** (`AssertionService.mint`): RS256, `kid` = RFC-7638-Fingerabdruck. Claims `iss`, `sub`, `name`, `roles` (nur Rollen aus
  `role_vocabulary`), `aud` = `[slug, "portal"]` (plus `"adapters"` bei Apps mit Adaptern), `azp`, `scp`, `iat`, `exp`, `jti`, `v: 1`.
  `email` fehlt noch, weil die Session keine Adresse speichert. Das Token steht weder im Log noch in der Fehlerseite.
- **JWKS:** `GET /.well-known/jwks.json` mit allen veröffentlichten Schlüsseln, `Cache-Control: public, max-age=300`. Apps setzen
  `PORTAL_API_URL` auf die Adresse des Portals.
- **Menü der App:** `GET /nav` nimmt `Authorization: Bearer <Token>` (Zielgruppe `portal`) an, übergangsweise auch `X-Portal-Assertion` (SDK bis 1.0.0-dev) und liefert das Menü für die Rollen im Token. Die Dateien
  des Kits liegen zusätzlich unter `kit.css`, `kit.js`, `icons.svg` und `<X-Portal-Kit>.js` (Cache `no-cache`).
- **Fehler:** Container nicht erreichbar oder Status `unhealthy` ergibt 503, Zeitüberschreitung 504, anderer Fehler 502, Body über
  `max_body_bytes` 413 (jeweils Fehlerseite im Portalrahmen).
- **Grenzen:** keine WebSockets, keine Lastverteilung, kein Schlüsselwechsel im Betrieb (nur `next`/`previous` vorbereitet). Prod ohne
  `signing_key_current` bricht den Start ab.

### Prüfanleitung (lokal, ohne VM)

1. App aus dem Golden Master starten, z. B. Python:
   `PORTAL_ENV=production PORTAL_SLUG=noten PORTAL_BASE_PATH=/apps/noten PORTAL_API_URL=http://localhost:8000 PORTAL_ISSUER=http://localhost:8000/ PORT=8080 uvicorn app.main:app --app-dir src --port 8080`
2. `make dev-apps`, als `alexandru` anmelden, `http://localhost:8000/apps/noten/` öffnen: Die App zeigt Name und Rollen.
3. App beenden und neu laden: Das Portal zeigt die 503-Seite.
4. Als `gast` anmelden: 403, die App bekommt keine Anfrage.
