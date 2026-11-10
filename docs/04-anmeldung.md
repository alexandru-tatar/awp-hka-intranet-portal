# 04 – Anmeldung

Das Portal kennt zwei Modi (`auth_mode`):

| Modus | Anmeldung | Sessions |
|---|---|---|
| `dev` (nur mit `env: dev`) | Auswahl der Testpersonen aus `dev/users.yml` | Speicher |
| `gateway` | keine eigene: Identität kommt vom separaten Security-Gateway (Repo `security-gateway`) | keine im Portal |

OIDC, Redis-Sessions, App-Proxy und Token-Ausstellung gehören nicht mehr zum Portal. Sie liegen im Gateway
(`security-gateway/docs/gateway-portal.md`).

## Modus `gateway`

Der Browser spricht nur mit dem Gateway. Dieses hält die Session und reicht jede Anfrage mit
`X-Portal-Assertion: <JWT>` an das Portal weiter. Das Portal (`auth/gateway.py`, `GatewayVerifier`)
- lädt nur öffentliche Schlüssel von `gateway.jwks_url` (max. 64 KiB, kein Redirect, 2 s Timeout, 300 s Cache),
- akzeptiert nur RS256 mit bekannter `kid`, `iss`, `aud` (Standard `hka-portal-ui`), `sub`, `roles`, `iat`, `exp`
  (≤ 300 s), `jti`, `v=1`, `token_use=portal-ui` und `csrf`,
- legt daraus einen unveränderlichen `GatewayUser` an (`request.state.gateway_user`); `/readyz` und `/internal/*`
  sind ausgenommen (eigene Service-Token-Prüfung),
- verlangt bei schreibenden Anfragen die exakte öffentliche Origin (`gateway.public_url`),
- gibt `/login`, `/logout`, `/apps/*` mit 404 zurück: das erledigt das Gateway,
- akzeptiert für `/nav` zusätzlich ein App-Token (`Authorization: Bearer`, `aud` enthält `portal`).

Das CSRF-Token der Formulare ist der Wert der Gateway-Session. Adminseiten bleiben rollen- und CSRF-geschützt.

Interne API für das Gateway (nur mit `PORTAL_REGISTRY_SERVICE_TOKEN_FILE`, Bearer-Service-Token):
`GET /internal/apps/{slug}/access` und `POST /internal/apps/{slug}/authorize`.

### Konfiguration

```yaml
env: prod
auth_mode: gateway
gateway:
  issuer: http://localhost:18080/
  jwks_url: http://gateway:8080/.well-known/jwks.json
  public_url: http://localhost:18080
  audience: hka-portal-ui
```

Beispiele: `dev/gateway.vm.yml` (Test-VM) und `security-gateway/deployment/portal.yml` (lokal).

## Modus `dev`

`GET /login` zeigt die Testpersonen, `POST /login` legt eine Session im Speicher an und setzt das Cookie
(`session_cookie`). `GET /logout` zeigt eine Bestätigung, `POST /logout` (mit CSRF-Token) beendet die Session.
Der Zielpfad `next` ist gegen Open Redirect geschützt (`auth/redirects.py`: nur `/` und `/apps/…`).
