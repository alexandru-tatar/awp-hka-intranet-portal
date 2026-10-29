# 05 – Compose

Jeder Dienst hat ein eigenes Verzeichnis unter `extras/compose/`; `server` startet alle zusammen.

```text
extras/compose/
├── redis/compose.yml       redis:8-alpine, 127.0.0.1:6379, ohne Persistenz
├── keycloak/               compose.yml, Dockerfile, hka-realm.json, theme/ (Login-Theme), 127.0.0.1:8180
├── backend/compose.yml     Portal (Dockerfile.trixie), 127.0.0.1:8000, Konfiguration dev/gateway.compose.yml
└── server/compose.yml      include: redis + keycloak + backend
```

## Starten

```sh
cd extras/compose/server && docker compose up --build     # oder: make server-up
docker compose down                                       # oder: make server-down
```

| Dienst | Adresse |
|---|---|
| Portal | http://localhost:8000 (Anmeldung: `alexandru`/`alexandru`, `admin`/`admin`, siehe [04](04-anmeldung.md)) |
| Keycloak | http://localhost:8180 (Konsole `admin`/`admin`) |
| Redis | `127.0.0.1:6379` |

Nur Redis und Keycloak (Portal läuft auf dem Host): `make idp-up`, dann `make dev-oidc`, am Ende `make idp-down`.
Nach dem Start braucht Keycloak etwa 15–20 Sekunden, bis die Anmeldung funktioniert.

## Hostnamen von Keycloak

Der Browser erreicht Keycloak als `localhost:8180`, das Backend im Compose-Netz als `keycloak:8080`. Damit der
`issuer` im Token trotzdem immer `http://localhost:8180/realms/hka` ist, setzt `keycloak/compose.yml`
`KC_HOSTNAME=http://localhost:8180` und `KC_HOSTNAME_BACKCHANNEL_DYNAMIC=true` (Token- und JWKS-URLs richten sich nach dem
Host der Anfrage). Das Backend liest die Discovery deshalb über `oidc.discovery_url`
(`http://keycloak:8080/realms/hka/.well-known/openid-configuration`) und prüft den `issuer` gegen `localhost:8180`.

## Fehlersuche

| Symptom | Ursache und Abhilfe |
|---|---|
| `port is already allocated` (6379, 8180, 8000) | Ein anderer Stack läuft noch (`docker ps`). `make server-down` bzw. `make idp-down`, nicht beide gleichzeitig starten |
| Login zeigt Keycloak-Fehler oder Verbindung verweigert | Keycloak startet noch, nach `up` etwa 20 Sekunden warten |
| Portal antwortet mit 503 | Redis nicht erreichbar (`/readyz` zeigt `check: redis`); `docker ps` prüfen |
| Nach Logout fragt Keycloak nicht nach dem Passwort | `post_logout_redirect_uri` fehlt in der Konfiguration oder ist im Client nicht erlaubt (siehe [04](04-anmeldung.md#abmelden)) |
| Änderung am Realm oder Theme ohne Wirkung | Image neu bauen: `make idp-up` bzw. `make server-up` |
| Logs | `docker compose -f extras/compose/server/compose.yml logs -f backend` (bzw. `keycloak`, `redis`) |

## Hinweise

- **Realm oder Theme geändert?** Beides ist im Image (`COPY` im `keycloak/Dockerfile`), nicht gemountet. Änderungen brauchen
  `--build` bzw. `make idp-up`.
- **Build-Kontext von Keycloak ist das Projektverzeichnis**, weil das Image das Design-Kit baut (`kit/` → `kit.css` des Themes).
  Was in den Kontext darf, steht in `keycloak/Dockerfile.dockerignore` (hat Vorrang vor der `.dockerignore` im Projektroot).
- **macOS und `~/Documents`:** Docker Desktop darf diesen Ordner standardmäßig nicht mounten
  (`operation not permitted`). Deshalb gibt es keine Bind-Mounts; Ordner mit Dateien gehören in den Build-Kontext.
- **Einzeln gestartet** findet das Backend Redis und Keycloak nicht (eigene Netze). Immer `server` oder die
  Make-Ziele benutzen.
- **Daten:** Redis speichert nichts auf Platte; nach einem Neustart sind alle Sessions weg.
