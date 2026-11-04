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

Der Status einer App kommt aus einer von zwei Quellen:

- **Statusdatei** (`state_file`, lokal): `dev/state.yml` ersetzt den Prober von Hand. Apps ohne Eintrag sind `healthy`.
- **Prober** (`registry.probe: true`, VM): Das Portal fragt `/healthz` jeder App und setzt den Status selbst. Dann gibt es keine
  Statusdatei (die Konfiguration lehnt beides zusammen ab).

```yaml
noten:        { status: healthy,   last_probe_at: "2026-10-26 09:14:02", last_deployed_at: "2026-10-20 16:03" }
raumbuchung:  { status: unhealthy, last_probe_at: "…",                   last_deployed_at: "…" }
```

| Status | Menü | `/apps/<slug>/` |
|---|---|---|
| `healthy` | ja, für passende Rollen | erreichbar |
| `unhealthy` | ja, mit dem Hinweis „nicht verfügbar“ | 503 (für Benutzer mit passender Rolle) |
| `registering`, `failed`, `retired` | nein | 404 |

Ein unbekannter Status wird ins Log geschrieben (`state_rejected`) und die App übersprungen.

## Registrierung durch die Pipeline (HKA-53)

Einfache Stufe der Registry (03 §4 bis §8, ohne SQLite und ohne Schnittstelle mit Token): Die Pipeline legt nach dem erfolgreichen
Deployment das geprüfte Manifest in den Manifest-Ordner auf der VM. Das Portal übernimmt es von selbst, ohne Neustart.

```text
Pipeline --ssh deploy@VM check/register--> portal-deploy --docker run--> python -m portal.registry
                                                                           |  schreibt <slug>.json + owners.json
Portal (Hintergrundaufgabe): Ordner alle 5 s prüfen --> registering --3 x /healthz 200--> healthy --> Menü
```

**Befehl** (`registry/__main__.py`, `registry/registration.py`): `python -m portal.registry {check|register} --config <yml> --owner <owner/repo>`,
das Manifest auf der Standardeingabe (höchstens 64 KiB).

| Schritt | Prüfung | Fehler |
|---|---|---|
| 1 | JSON, Schema, reservierter Slug, Rollen aus `role_vocabulary`, Adapter-Scopes aus `adapter_scopes` (derselbe `ManifestValidator` wie im Portal) | **PF-104** mit Pointer, Meldung, erlaubten Rollen und Kategorien |
| 2 | Besitzer: Der erste `--owner` eines Namens bleibt es (`registry.owners_file`, `{slug: owner}`); ein Name, der von Hand eingerichtet wurde oder in einer zweiten Datei steht, ist belegt | **PF-202** |
| 3 | Nur `register`: Sperre (`owners.json.lock`, `flock`, wartet bis 10 s) | **PF-204** |
| 4 | Nur `register`: erst `owners.json`, dann `<slug>.json`, beide atomar (Hilfsdatei + `os.replace`, Rechte 0644) | Exit 3 bei Schreibfehler |

`check` macht die Schritte 1 und 2 und schreibt nichts. Bei jeder Ablehnung bleibt jede Datei unverändert, also auch das Menü. Die
Fehlerblöcke stehen im Format des Katalogs der Pipeline (`.agents/skills/pipeline-fehler/fehlercodes.md`) auf der Fehlerausgabe.
Exit-Codes: 0 in Ordnung, 1 abgelehnt, 2 falscher Aufruf, 3 Fehler im Betrieb (Konfiguration, Besitzerdatei, Schreibrechte).

**Nachladen:** Eine Hintergrundaufgabe des Portals ruft alle `registry.refresh_seconds` (Standard 5) `Registry.refresh()` auf, in jeder
Umgebung. Wird dieselbe Datei neu geschrieben (anderer Inhalt oder neue Änderungszeit), gilt das als neue Registrierung, und die App
beginnt wieder bei `registering`.

**Prober** (`registry/prober.py`): `GET <apps.upstream>/healthz` mit 2 s Zeitlimit, ohne Token, ohne Cookie, ohne Weiterleitung; nur
200 zählt, der Body wird nicht gelesen. Höchstens 4 Prüfungen gleichzeitig.

| Von | Nach | Bedingung | Abstand danach |
|---|---|---|---|
| `registering` | `healthy` | 3 Erfolge in Folge | 30 s |
| `registering` | `failed` | 60 s ohne 3 Erfolge | 30 s |
| `healthy` | `unhealthy` | 3 Fehler in Folge | 10 s |
| `unhealthy` | `healthy` | 1 Erfolg | 30 s |
| `failed` | `registering` | 1 Erfolg | 2 s |

In `registering` wird alle 2 s geprüft. Gemessen lokal (Python-App aus dem Golden Master, Portal mit Prober): neues Manifest bis
Menüeintrag 5 s, Container gestoppt bis „nicht verfügbar“ 42 s, Container wieder da bis zurück im Menü ohne Hinweis 7 s.

**Abweichungen von 03 §7:**

- Unhealthy-Apps stehen **im Menü** mit dem Hinweis „nicht verfügbar“ (Text und Farbe, `badge--unhealthy`), nicht versteckt. So verlangt es
  HKA-53 (AK2). Der Link führt auf die 503-Seite.
- Nach einem Fehler in `healthy` folgt die nächste Prüfung nach 10 s statt nach 30 s. `unhealthy` steht dann nach etwa einer halben
  Minute da, nicht erst nach eineinhalb.
- `failed` wird alle 30 s weiter geprüft (03: keine Prüfung mehr). So kommt eine App nach einem Neustart der VM von selbst zurück.
- Kein Jitter. Nach einem Neustart des Portals beginnen alle Apps bei `registering` und sind nach etwa 5 s wieder im Menü.
- Nicht geprüft: Versionsrückschritt (03 §5, 422), `rollback`, Abmelden, Sperrfrist für Namen (Phase 3).

**Konfiguration** (`dev/gateway.vm.yml` ist das Beispiel): 

```yaml
registry:
  refresh_seconds: 5          # Abstand, in dem der Manifest-Ordner geprüft wird (mindestens 1)
  probe: true                 # Prober an: verlangt den Abschnitt apps, schließt state_file aus
  owners_file: /var/lib/portal/registry/owners.json   # nur der Befehl benutzt die Datei
```

Einrichtung auf der VM, Schlüssel je App-Repository und Testanleitungen: [`extras/compose/vm/deploy/README.md`](../extras/compose/vm/deploy/README.md).

## Menü und Zugriff

- **Menü** (`AppService.find_nav_groups`): gesunde und gestörte Apps (`unhealthy`, mit „nicht verfügbar“), die mindestens eine Rolle mit dem Benutzer teilen; Kategorien in fester
  Reihenfolge (Studium, Verwaltung, Kommunikation, Sonstiges), Einträge alphabetisch (Umlaute wie Grundbuchstaben); leere
  Kategorien entfallen.
- **Zugriff auf eine App** (`AppService.find_authorized`): Reihenfolge und Fehlerseiten siehe
  [03 Service und Router](03-service-und-router.md#zugriffsentscheidung-für-apps).
- **Statusseite** `/_portal/status`: alle Apps mit Version, Status und Zeitpunkten, nur für `platform-admin`.

## Registry-Quelle austauschen

Eine Quelle erfüllt das Protocol `RegistrySource` (`registry/sources.py`):

- `load() -> dict[str, AppView]`: alle Apps laden,
- `fingerprint() -> Hashable`: ändert sich, sobald `load()` etwas anderes liefern würde.

`ManifestDirectorySource` (Ordner mit JSON-Dateien plus `state.yml`, oder mit `probe` plus Prober) ist der Ersatz für die SQLite-Registry. Eine neue Quelle wird in
`context.py` (`_build_registry`) verdrahtet; Menü, Zugriff und Statusseite ändern sich dadurch nicht.

## Snapshot

`Registry` hält den aktuellen `Snapshot` (laufende Nummer plus Apps nach Slug). Leser sperren nie; `reload()` tauscht die Referenz
unter einem Lock aus (`snapshot_swapped version=… apps=…` im Log). `refresh()` lädt nur, wenn sich der `fingerprint()` geändert hat.
Mit Prober (`keep_status`) behält eine App beim Neuladen Status und letzte Prüfung, solange ihre Registrierung (Manifest und Zeitpunkt der
Bereitstellung) gleich ist; `set_status()` tauscht den Snapshot für den Prober und ignoriert eine Prüfung, die zu einer älteren
Registrierung gehört.

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
