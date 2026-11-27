# 05 – Compose

Das Portal hat keinen eigenen Stack mehr: Anmeldung, Sessions (Redis), Keycloak und App-Routing gehören zum
**Security-Gateway** (Repo `awp-hka-security-gateway`). Dessen `server/compose.yml` (lokal) und `vm/compose.yml`
(Test-VM) binden per `include` die Bausteine aller Repos ein; aus diesem Repo kommt nur das Portal-Backend.

```text
extras/compose/
├── backend/   compose.yml: Dienst "backend" (Portal im Gateway-Modus), eingebunden vom Security-Gateway
└── vm/        Test-VM: nginx-portal.conf (nginx davor) und deploy/ (Apps registrieren mit portal-deploy)
```

## Lokal starten

Im Gateway-Repo (Repos nebeneinander geklont, Einzelheiten in dessen README, Abschnitt „Erster Start“):

```sh
make server-init    # einmalig: Secrets, server/.env, Portal-Ordner .local/portal/{manifests,status,registry}
make server-up      # Gateway, Redis, Keycloak, Portal (backend), Adapter; baut die Images
make server-down
```

Portal: http://localhost:18080 (über das Gateway; das Portal hat keinen Hostport). Apps kommen mit
`make deploy-local` aus ihrem eigenen Repo in das Netz `hka-portal-apps`.

## Der Dienst `backend`

| Wert | Lokal (Standard) | VM (`vm/.env` im Gateway-Repo) |
|---|---|---|
| Image | `hka/portal:local`, gebaut mit `Dockerfile.local` (öffentliche Basisimages) | `hka/portal:<PORTAL_IMAGE_TAG>`, gebaut mit `Dockerfile` (gehärtet), auf der VM nur geladen |
| Konfiguration (`PORTAL_CONFIG`) | `/opt/app/dev/gateway.compose.yml` | `/opt/app/dev/gateway.vm.yml` |
| Daten (Manifeste, Status, Registry) | `.local/portal/*` in diesem Repo | `/srv/portal/*` |
| Dokumentation (Seiten, Versionen, Bilder) | `.local/portal/registry/docs` | `/srv/portal/registry/docs` (im Registry-Volume, kein eigenes Volume nötig) |
| Service-Token für die Registry-API | `server/.secrets/registry-service-token` | `/srv/portal/gateway/secrets/registry-service-token` |

Die Konfigurationen sind ins Image eingebaut: Nach Änderungen an `dev/gateway.compose.yml` oder `dev/gateway.vm.yml`
das Image neu bauen (`make server-up` bzw. `make vm-images`). Netze: `portal` (nur Gateway ↔ Portal) und
`hka-portal-apps` (Prober → `/healthz` der Apps). Kein Redis, kein Keycloak, kein Signierschlüssel im Portal.

## Hostnamen von Keycloak

Keycloak läuft im Gateway-Projekt. Der Browser sieht ihn lokal als `http://localhost:8180` (Issuer
`http://localhost:8180/realms/hka`), auf der VM über nginx als `https://<vm>/auth` (Issuer
`https://<vm>/auth/realms/hka`). Das Gateway holt Discovery, Token und Schlüssel intern über `keycloak:8080`
(`KC_HOSTNAME_BACKCHANNEL_DYNAMIC`). Das Portal spricht nie mit Keycloak.

Realm, Testpersonen und Login-Theme liegen in `awp-hka-security-gateway/keycloak/`. Das Theme nutzt eine Kopie
des Design-Kits: hier `make keycloak-theme-release`, dort `make keycloak-theme-update THEME_DIST=…`.

## Fehlersuche

- **Portal antwortet 401 / Gateway 503:** Issuer, Audience und JWKS-URL in `dev/gateway.compose.yml` müssen zum
  Gateway passen (siehe Kommentar in der Datei); Service-Token gleich bei Gateway und Portal.
- **Portal startet nicht, `manifests_dir` fehlt:** Ordner `.local/portal/*` fehlen; `make server-init` im Gateway.
- **App fehlt im Menü:** `make deploy-local` in der App, dann `docker compose -f server/compose.yml logs backend`
  (im Gateway-Repo) nach `registry_change` durchsuchen.
