# 05 – Compose

Das Portal hat keinen eigenen Redis-, OIDC- oder Backend-Stack mehr. Login, Sessions (Redis) und App-Routing laufen im
separaten Repo `security-gateway` (`compose.yml` + `compose.portal.yml`, siehe dessen `docs/gateway-portal.md`); dieses
Compose startet auch das Portal (mit `Dockerfile.local`) und die Test-App.

```text
extras/compose/
├── keycloak/   compose.yml, Dockerfile, hka-realm.json, theme/ (Login-Theme), 127.0.0.1:8180
└── vm/         Test-VM (nginx, Deploy-Skripte, compose.yml)
```

## Keycloak für das Gateway

```sh
make idp-up      # oder: cd extras/compose/keycloak && docker compose up --build -d
make idp-down
```

Konsole http://localhost:8180 (`admin`/`admin`). Benutzer = Passwort: `alexandru`, `antonio`, `david`, `neumann`, `max`,
`admin`, `gast`. Der Client `portal` erlaubt Redirect `http://localhost:18080/oidc/callback` (Gateway) und
Post-Logout `http://localhost:18080/`. Docker-Netz `hka-portal-keycloak_default` ist `GW_KEYCLOAK_NETWORK` im Gateway.
Nach dem Start braucht Keycloak etwa 15–20 Sekunden.

- **Realm oder Theme geändert?** Beides ist im Image (`COPY` im `keycloak/Dockerfile`), nicht gemountet. Änderungen brauchen `--build`.
