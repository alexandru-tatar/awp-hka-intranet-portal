# HKA Portal — Portal-UI und Design-Kit

Umsetzung der Frontend-Teile aus `claude-proposal/04-portal-ui-and-design-kit.md`, vorbereitet für
App-Manifeste nach `claude-proposal/03-registry.md` §3 (alle Spezifikationen: `claude-proposal/`). Server-gerendertes HTML (FastAPI + Jinja2),
kein JS-Framework, ein Skript < 1 KB für Dialoge.

## Start

```sh
make setup   # uv sync: .venv + Abhängigkeiten (uv.lock)
make dev     # baut das Kit, startet http://127.0.0.1:8000
make test    # Kontrast-Gate + pytest
```

Standardmäßig (`auth_mode: dev`) ersetzt eine Auswahl von Testpersonen (`dev/users.yml`) die OIDC-Anmeldung.

Mit echter Anmeldung (`auth_mode: oidc`: Keycloak als IdP, Sessions in Redis; braucht Docker):

```sh
make idp-up    # Redis :6379 + Keycloak :8180 (Realm hka; Benutzer = Passwort: alexandru, antonio, david, neumann, max, admin, gast)
make dev-oidc  # Portal auf dem Host mit dev/gateway.oidc.yml, :8000 (passt zur redirect_uri)
make idp-down
```

Oder alles im Container (Redis, Keycloak, Portal-Backend):

```sh
make server-up   # oder: cd extras/compose/server && docker compose up --build
make server-down
```

## Aufbau

```
pyproject.toml                 Paket, Abhängigkeiten (uv), pytest-Konfiguration
uv.lock                        GENERIERT durch uv – nicht von Hand editieren
claude-proposal/               Spezifikationen 02–10 und Architekturvorschlag (Vorgabe, nicht ändern)
docs/                          Entwicklerdokumentation (Architektur, Entwicklung, Anmeldung, Compose)
schemas/manifest.schema.json   Vertrag #2: ein Schema für Pipeline, Registry, SDK
kit/                           Design-Kit (04 §11)
  css/                         tokens · base · layout · components · print
  js/kit.js                    Dialog-Muster (≤ 1 KB, wird beim Build geprüft)
  icons/icons.svg              Icon-Allow-List = enum menu.icon im Schema
  pairs.json, tools/contrast.py  Kontrast-Gate (bricht den Build ab)
  tools/build.py               → kit/dist/kit-<hash>.css/js, kit-manifest.json
src/portal/
  app.py                       create_app(): nur Verdrahtung
  context.py                   Portal-Kontext (Config, Kit, Texte, Registry, Sessions, Views)
  core/                        config · i18n · kit (Asset-URLs)
  registry/                    models · validation (Manifest) · sources (JSON-Ordner) · store (Snapshot)
  auth/                        sessions (Protocol + Memory) · redis_sessions · oidc · roles · dev_users · redirects
  service/                     Geschäftslogik + DTOs: AppService, SessionService, SessionWriteService, exceptions
  web/                         views (Rendern) · menu · deps (Session/Rolle/Services) · errors · middleware
  router/                      page · auth · nav · health · oidc (auth_mode oidc) · dev_login (auth_mode dev) · dev (env dev) · constants
  locales/messages.de.yml      alle UI-Texte
  templates/                   base, partials, pages, macros (Feld, Dialog, Tabelle)
dev/
  gateway.dev.yml              Konfiguration für lokal
  manifests/*.json             ein Manifest pro App  ← hier neue Apps anlegen
  state.yml                    Status je App (healthy/unhealthy/…), bis es den Prober gibt
  users.yml                    Testpersonen mit Rollen
  gateway.oidc.yml             Konfiguration für Anmeldung über Keycloak + Redis
  roles.yml · grants.yml       IdP-Claims → Rollen (02 §8), zusätzliche Rollen je Subject
  keycloak/portal-client-secret  Client-Secret des dev-IdP (nur dev!)
  gateway.compose.yml          Konfiguration für das Backend im Container
extras/compose/                Docker Compose je Baustein
  redis/ · keycloak/ · backend/  je eine compose.yml (keycloak/ mit Dockerfile + hka-realm.json)
  server/                      compose.yml bindet alle drei ein: docker compose up startet alles
Dockerfile                     Portal-Image (dhi.io, braucht Login) · Dockerfile.trixie: ohne dhi
tests/                         UI1–UI14 (soweit ohne Browser prüfbar), REG4/5, Kit, Service, Fehlerseiten, OIDC (G2/G4/G6)
```

## Eine App hinzufügen

Datei `dev/manifests/<slug>.json` anlegen und Seite neu laden — im Dev-Modus wird der
Ordner bei jeder Anfrage auf Änderungen geprüft.

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

Geprüft wird: Schema (unbekannte Felder sind Fehler), reservierte Slugs, Rollen gegen
`role_vocabulary`, Adapter-Scopes gegen `adapter_scopes`. Ungültige Manifeste werden mit
JSON-Pointer im Log gemeldet und übersprungen. Menü zeigt nur Apps mit Status `healthy`
und passender Rolle; Kategorien in fester Reihenfolge, Einträge alphabetisch.

## Was echt ist und was Platzhalter

| Teil | Jetzt | Später |
|---|---|---|
| Seiten, Kit, Texte, `/nav` mit ETag + `X-Portal-Kit` | wie spezifiziert | — |
| Registry | `ManifestDirectorySource` liest JSON-Dateien | SQLite-Registry implementiert `RegistrySource.load()` (03 §2) |
| Status / Probe | `dev/state.yml` | Prober im Gateway (03 §7) |
| Anmeldung | `auth_mode: dev`: Testpersonen-Auswahl; `auth_mode: oidc`: Keycloak, Authorization Code + PKCE, ID-Token-Prüfung nach 02 §5 | Shibboleth-OIDC: `issuer`, Client und `roles.yml` tauschen |
| Sessions | Redis (`RedisSessionStore`), wenn `redis_url` gesetzt ist; sonst im Speicher | — |
| `/nav`-Auth | Session-Cookie | `Authorization: Bearer <assertion>` auf :8001 |
| `/apps/<slug>/` | Platzhalter-Seite mit den Kit-Mustern, gleiche Entscheidungsreihenfolge wie `/auth/verify` | Traefik routet zur App |

## Offene Punkte (aus 04 §13)

- `{kontakt}` und Links für Hilfe/Datenschutz/Impressum — in `dev/gateway.dev.yml` Platzhalter.
- Design: angelehnt an www.h-ka.de (HKA-Rot `#d72305`, eckige Formen, graue Kacheln, fette
  Mono-Links mit „>"). Schrift IBM Plex Sans (wie h-ka.de); für die lizenzpflichtige GT Pressura
  stehen IBM Plex Sans Condensed (Überschriften) und IBM Plex Mono (Buttons) — alle OFL, selbst
  gehostet in `kit/fonts/`. Logo/Wortmarke nur als Text; offizielles Logo und Pressura-Lizenz kommen
  mit dem Designhandbuch → Token-Werte in `kit/css/tokens.css` tauschen, `make contrast` erneut.
- Abweichung: `icons.svg` wird wie CSS/JS mit Hash ausgeliefert (`icons-<hash>.svg`), damit
  `immutable`-Caching bei Icon-Änderungen nicht veraltet.
- Noch nicht umgesetzt: axe/Playwright-Gates und visuelle Regression (04 §9–10), Stylelint
  (ersatzweise Test „kein Hex außerhalb `tokens.css`").
