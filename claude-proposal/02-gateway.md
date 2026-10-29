# 02 — Gateway

Implementation-level specification. Overview: `../09-component-design.md` §2. Names, ports, subnets: `README.md`. ⚑ = confirm against pinned versions.

## 1. Purpose and boundaries

The gateway is the **only** component that talks to the identity provider, owns sessions, decides authorization, and signs identity. One codebase, one process, four jobs: OIDC client, session/authorization service (`/auth/verify`), registry + Traefik config source (`03-registry.md`), portal UI (`04-portal-ui-and-design-kit.md`).

| Property | Value |
|---|---|
| Stack | Python 3.12, FastAPI, uvicorn, Jinja2, redis-py (asyncio), PyJWT + cryptography, httpx, jsonschema, PyYAML |
| **Workers** | **exactly one** (R14). The registry snapshot, mint cache and rate counters live in process memory; a second worker would silently serve stale routes and double-mint. Concurrency comes from asyncio. Sized for dozens of users. |
| Networks | `ingress` (172.29.10.2), `core` (172.29.12.3, Redis), `apps` (172.29.11.2), `egress` (172.29.13.2, IdP only; host-firewalled) |
| Listeners | **main** `172.29.10.2:8000` (ingress only); **apps-facing** `172.29.11.2:8001` (apps only) — R11/R23 |
| User / FS | uid 10001, `read_only: true`, writable: `/var/lib/portal` (registry DB), `/tmp` |

**R23 — listener binding.** A container with an IP on `apps` is reachable on *every* port it listens on. Binding uvicorn to `0.0.0.0:8000` would expose `/auth/verify` and `/registry/*` to every app. Therefore the two listeners bind to the two fixed container IPs above (static `ipv4_address` in Compose), and every handler on :8000 additionally rejects a peer address outside `172.29.10.0/29` (defence in depth, one line in a middleware).

## 2. Configuration — `gateway.yml`

```yaml
env: prod                                   # prod | stage
public_host: portal.hka.example
allowed_hosts: [portal.hka.example]

listen:
  main:      { host: 172.29.10.2, port: 8000 }
  apps_api:  { host: 172.29.11.2, port: 8001 }
  main_peer_cidr: 172.29.10.0/29

oidc:
  issuer: https://idp.hka.example/idp       # discovery: <issuer>/.well-known/openid-configuration
  client_id: portal
  client_auth: client_secret_basic          # or private_key_jwt
  client_secret_file: /run/secrets/oidc_client_secret
  redirect_path: /oidc/callback
  scopes: [openid, profile, email, eduperson]   # exact scope names depend on attribute release (open, 02-open-questions §1)
  id_token_algs: [RS256, ES256]             # pinned allow-list
  clock_leeway_seconds: 60
  use_userinfo_if_claims_missing: true      # one call at login, token then discarded; no refresh token kept

session:
  cookie_name: "__Host-portal_sid"
  login_cookie_name: "__Host-portal_login"
  idle_seconds: 1800
  absolute_seconds: 28800
  touch_min_interval_seconds: 60
  login_state_ttl_seconds: 600

redis:
  url: redis://redis:6379/0
  password_file: /run/secrets/redis_password

assertion:
  issuer: https://portal.hka.example/
  ttl_seconds: 60
  signing_key_current: /run/secrets/jwt_current.pem
  signing_key_next:    /run/secrets/jwt_next.pem        # optional: published in JWKS before use
  signing_key_previous: /run/secrets/jwt_previous.pem   # optional: still published after rotation
  mint_cache_margin_seconds: 15

roles:
  mapping_file: /etc/portal/roles.yml
  grants_file:  /etc/portal/grants.yml

registry:
  db_path: /var/lib/portal/registry.db
  registrar_token_file: /run/secrets/registrar_token
  probe: { path: /healthz, timeout_seconds: 2, healthy_interval: 30, unhealthy_interval: 10, fail_threshold: 3 }
  slug_cooldown_days: 90

security:
  h4_csrf_check: true
  h5_fetch_metadata_gate: false             # enable after the Durchstich (09 §1.5)
  login_rate_per_ip_per_5min: 20

logging: { level: INFO, format: json }
```
Validation at start: every referenced file must exist and be readable; every `listen.*.host` must be an address of a local interface; unknown keys are an error (typos fail fast, same stance as the manifest schema).

## 3. Endpoints

| Method + path | Listener | Auth | Purpose |
|---|---|---|---|
| `GET /` | main | session | portal home (`04`) |
| `GET /login` | main | none | start OIDC (§4) |
| `GET /oidc/callback` | main | login cookie + `state` | finish OIDC (§4) |
| `GET /logout` | main | session | confirmation page with the CSRF-protected form |
| `POST /logout` | main | session + CSRF token | end the portal session |
| `GET /auth/verify` | main | forwardAuth (peer = Traefik) | authorization decision (§6) |
| `GET /internal/traefik-config` | main | peer = Traefik | HTTP-provider payload (`01` §5) |
| `GET /_portal/*` | main | session (status, connections) / none (static, error) | portal pages and assets (`04`) |
| `PUT/GET/DELETE /registry/…` | main | `Authorization: Bearer <registrar token>` | registry API (`03`) |
| `GET /healthz` | main | none (peer-restricted) | liveness (§11) |
| `GET /readyz` | main | none (peer-restricted) | readiness (§11) |
| `GET /.well-known/jwks.json` | apps-facing | none (public keys) | verification keys for SDKs |
| `GET /nav` | apps-facing | `Authorization: Bearer <assertion>` with `aud ∋ portal` | role-filtered nav fragment for `layout()` (R11) |

Only the `portal` router rows in `01` §6 are reachable from outside; `/auth/verify`, `/internal/*`, `/registry/*`, `/healthz`, `/readyz` are not routed.

## 4. OIDC login — step by step (R13)

```text
GET /login?next=<path>
  1. rate-limit by peer IP (rl:login:{ip}); over limit -> 429 page
  2. next := sanitize(next)
       accept only: starts with "/", not "//", no backslash, no "\r\n", length <= 512,
                    path begins with "/apps/" or equals "/"
       otherwise next := "/"
  3. lid   := 128 random bits (url-safe)             # "login id"
     state := 128 random bits ; nonce := 128 random bits ; verifier := 256 random bits (PKCE)
  4. redis SETEX oidc:{lid} 600 {state, nonce, verifier, next}
  5. Set-Cookie: __Host-portal_login=<lid>; Secure; HttpOnly; SameSite=Lax; Path=/; Max-Age=600
  6. 302 -> <authorization_endpoint>
       ?response_type=code &client_id &redirect_uri &scope
       &state &nonce &code_challenge=S256(verifier) &code_challenge_method=S256

GET /oidc/callback?code&state     (or ?error=...)
  1. lid := cookie __Host-portal_login ; if missing -> error page "Anmeldung abgelaufen" (400)
  2. rec := redis GETDEL oidc:{lid} ; if missing or rec.state != query.state -> 400   # binds callback to THIS browser
  3. if ?error -> error page (no details echoed)
  4. token response := POST token_endpoint {grant_type=authorization_code, code, redirect_uri, code_verifier}
       client auth per config; timeout 5 s; one retry on 5xx
  5. validate id_token (§5)
  6. claims := id_token claims (+ userinfo once if configured and roles/affiliation missing)
  7. roles := map_roles(claims)                       # §8
  8. DELETE any existing cookie session of this browser (rotation): new sid := 256 random bits
  9. redis HSET sess:{sid} {sub, name, roles, amr, created=now, last_seen=now, csrf=<128 random bits>}
     EXPIRE sess:{sid} idle_seconds ; SADD usr:{sha256(sub)}:sessions sid
 10. Set-Cookie: __Host-portal_sid=<sid>; Secure; HttpOnly; SameSite=Lax; Path=/   (session cookie, no Max-Age)
     Set-Cookie: __Host-portal_login=; Max-Age=0
 11. 302 -> rec.next
```
Why the browser-binding cookie: with `state` stored only in Redis, an attacker can start a login in their own browser, then trick a victim's browser into hitting `/oidc/callback?code=<attacker's>&state=<attacker's>` and log the victim into the attacker's session (login CSRF). Requiring the callback to present the `lid` cookie that this browser received at `/login` closes that.

Access and refresh tokens from the IdP are **not stored**. The portal session is entirely local; IdP-side changes (role change, deactivation) take effect at the next login, at most `absolute_seconds` (8 h) later. For incident response use `revoke-sessions` (§9).

## 5. ID-token validation checklist

| Check | Rule |
|---|---|
| Signature | key from the IdP's JWKS (discovered, cached 10 min, refetched once on unknown `kid`); `alg ∈ id_token_algs`; reject `none` and HMAC |
| `iss` | equals configured issuer exactly |
| `aud` | contains `client_id`; if multiple, `azp == client_id` |
| `exp` / `iat` | `exp > now − leeway`; `iat ≤ now + leeway` (leeway 60 s) |
| `nonce` | equals the stored nonce |
| `sub` | present, non-empty |
| `amr` / `acr` | stored for display/audit only; not enforced (the new Shibboleth is MFA by policy) |

Any failure: log `login_failure{reason}`, show the generic "Anmeldung nicht möglich" page, do not reveal which check failed.

## 6. `/auth/verify`

Input headers set by Traefik: `X-Forwarded-Uri`, `X-Forwarded-Method`, `X-Forwarded-Host`, `X-Forwarded-Proto`; plus the original `Cookie`, `Accept`, `Origin`, `Referer`, `Sec-Fetch-*`.

```text
verify(req):
  rid  := new request id (or incoming X-Request-Id if valid, <=64 chars [A-Za-z0-9-])
  host := req.X-Forwarded-Host ; if host not in allowed_hosts -> 421
  uri  := req.X-Forwarded-Uri  ; path := urlsplit(uri).path
  m    := match(path, ^/apps/([a-z][a-z0-9-]{2,30})(/|$))          # segment-exact (R12)
  if not m -> 404
  slug := m[1]

  snap := registry.snapshot()                                      # immutable dict, swapped atomically (R14)
  app  := snap.get(slug)
  if app is None or app.status in (retired, failed) -> 404 (page)

  sid  := parse cookie __Host-portal_sid ; must match ^[A-Za-z0-9_-]{43}$
  sess := redis HGETALL sess:{sid} if sid else None
  if sess is None or now - sess.created > absolute_seconds:
        if sess: delete session
        return deny_unauthenticated(req, uri)
  touch(sess)                                                      # EXPIRE idle; at most once per touch_min_interval

  if roles(sess) ∩ app.roles = ∅ -> audit(verify_deny_role); 403 (page)
  if app.status != healthy        -> 503 (page "App vorübergehend nicht verfügbar")     # after the role check: no info leak
  if method not in (GET, HEAD, OPTIONS) and cross_site(req, host) -> audit(verify_deny_csrf); 403
  if cfg.h5 and not navigation(req) and not referer_ok(req, host, slug) -> audit(verify_deny_h5); 403

  token := mint_cache[(sid, slug)] if valid for > margin else mint(sess, app)
  return 200, headers { X-Portal-Assertion: token, X-Request-Id: rid }

deny_unauthenticated(req, uri):
  if method == GET and "text/html" in Accept and Sec-Fetch-Mode in (navigate, absent):
       return 302 /login?next=urlencode(path+query)
  return 401 application/problem+json

cross_site(req, host):
  sfs := req.Sec-Fetch-Site
  if sfs in (same-origin, none): return false
  if sfs present (same-site, cross-site): return true
  origin := req.Origin
  if origin present and origin != "https://" + host: return true
  return false                          # no browser signal at all: not a CSRF vector

navigation(req): Sec-Fetch-Mode == navigate and Sec-Fetch-Dest in (document, empty-absent)
referer_ok(req, host, slug): Referer present and starts with "https://"+host+"/apps/"+slug+"/" or "https://"+host+"/"
```
Notes:
- The role check precedes the health check, so an unauthorized visitor learns nothing about an app's operational state.
- A request carrying a valid session but a **foreign** `Origin` on a `POST` is rejected even if it came from a legitimate browser tab on another site — that is the point.
- The decision is the same whether the path is the app root or a deep asset URL; the mint cache keeps asset-heavy pages from signing dozens of JWTs (§7).
- Every 4xx/5xx path writes a structured log line (§10) but **never** the cookie value or the assertion.

## 7. Assertion minting and key management

```text
mint(sess, app):
  claims := {
    iss, sub: sess.sub, roles: sorted(roles(sess) ∩ platform_roles),
    aud:   [app.slug, "portal"] + (["adapters"] if app.adapters else []),
    azp:   app.slug,
    scp:   app.adapters,                    # granted adapter scopes, e.g. ["noten:read"]
    iat: now, exp: now + ttl, jti: uuid4, v: 1
  }
  claims.name = sess.name                               # default claim set: sub, name, roles
  if "email" in app.claims: claims.email = sess.email   # only if the manifest asked (data minimisation)
  header := {alg: RS256, typ: "JWT", kid: <RFC 7638 thumbprint of current key>}
  token  := sign(header, claims)
  mint_cache[(sid, app.slug)] := (token, exp)        # cache evicted at exp - margin; also on logout / role change
  return token
```
- **Key pair:** RSA 3072 (RS256). Generated once by `platform.sh bootstrap`, stored as `jwt_current.pem` (0400, root) and mounted as a Docker secret.
- **JWKS** publishes `current`, plus `next` and `previous` when present, each with its `kid`; response is cacheable (`Cache-Control: public, max-age=300`).
- **Rotation (scripted by `platform.sh rotate-key`, `10-platform-ops.md`):**
  1. generate `jwt_next.pem`; restart gateway → JWKS now lists current + next;
  2. wait ≥ 10 minutes (SDK JWKS caches are 5 minutes);
  3. promote: `current → previous`, `next → current`; restart gateway → signing switches;
  4. wait 24 hours (far beyond the 60-second lifetime; covers slow caches);
  5. delete `jwt_previous.pem`; restart gateway.
  No user is logged out at any step.
- **Lost key:** generate a new `current`, restart. SDKs refetch on the unknown `kid`; in-flight assertions (≤ 60 s) fail once and retry.
- The signing key never leaves the gateway container. Starters and adapters hold public keys only.

## 8. Roles

```yaml
# /etc/portal/roles.yml — maps IdP attribute values to platform roles
sources:
  - claim: eduPersonAffiliation          # list or string
    map: { student: student, employee: employee, faculty: professor, staff: employee }
  - claim: eduPersonEntitlement
    map: { "urn:hka:portal:admin": platform-admin }
default_roles: []                        # a user with no mapped role sees an empty menu, never "everyone"
```
```yaml
# /etc/portal/grants.yml — per-subject additions maintained by the team / HKA-IT
grants:
  - sub: "7c1e…"        # IdP subject
    roles: [pilot-tester]
    note: "Pilot 2027, Fachexperte Studienbüro"
```
Worked example: IdP sends `eduPersonAffiliation=[employee, staff]`, subject has a grant `pilot-tester` → roles `{employee, pilot-tester}`. An app with `roles: ["student"]` is invisible and returns 403 for this user; one with `roles: ["employee"]` is visible.

Honest limit: **a manifest may only reference roles this mapper can produce.** Per-app fine-grained roles (the client's `namespace:role:permission` convention from 15.10) need the AF-11 decision; until then the mapper's vocabulary is the contract. `platform-admin` gates `/_portal/status`.

Roles are computed at login and stored in the session; `grants.yml` edits apply at the next login, or immediately after `revoke-sessions`.

## 9. Logout and session revocation

- `POST /logout`: requires the form field `csrf` equal to `sess.csrf`. Deletes `sess:{sid}`, removes `sid` from `usr:{sha256(sub)}:sessions`, evicts mint-cache entries for `sid`, clears the cookie, redirects to `/`. No IdP single logout (not required, `02-open-questions.md` §1).
- `gateway-cli revoke-sessions --sub <sub>` (run with `docker compose exec gateway …`): deletes every session listed in `usr:{sha256(sub)}:sessions`. For a compromised account or an urgent role change. `revoke-sessions --all` for a platform-wide reset.

## 10. Logging and audit events

JSON lines on stdout. **Never logged:** cookie values, assertions, ID tokens, codes, secrets, email addresses.

| Event | Level | Fields |
|---|---|---|
| `login_start` | INFO | `request_id`, `ip` |
| `login_success` | INFO | `request_id`, `sub_hash`, `roles`, `amr` |
| `login_failure` | WARN | `request_id`, `reason ∈ {state, nonce, signature, iss, aud, exp, token_endpoint, rate_limit}` |
| `logout` | INFO | `sub_hash`, `sid_hash` |
| `verify_allow` | DEBUG | `slug`, `sid_hash`, `request_id` |
| `verify_deny` | INFO | `reason ∈ {unauth, role, csrf, h5, unhealthy, unknown_slug, host}`, `slug`, `sid_hash` |
| `registry_change` | INFO | `action`, `slug`, `actor` |
| `config_generator_rejected` | ERROR | `slug`, `reason` |
| `key_loaded` | INFO | `kid_current`, `kid_next`, `kid_previous` |
| `redis_unavailable` | ERROR | `op` |

`sub_hash` = first 16 hex chars of `HMAC-SHA256(audit_hmac_key, sub)` (R19); `sid_hash` the same construction over the session id.

## 11. Health and readiness

- `/healthz`: process up and event loop responsive → 200.
- `/readyz`: Redis `PING` ok **and** registry DB readable **and** signing key loaded **and** IdP discovery cached at least once → 200, else 503 with the failing check named. Compose uses `/readyz` as the healthcheck (`depends_on: service_healthy` for Traefik).

## 12. When origin-per-app arrives (R3, Phase 4)

Under `https://<slug>.apps.<domain>/` the session cookie cannot be shared (`__Host-` cookies are host-only), which is the point. The gateway gains `GET /apps-sso?app=<slug>` (portal origin): it creates a 30-second, single-use `code` in Redis bound to `(sid, slug)`, redirects to `https://<slug>.apps.<domain>/_sso?code=…`; `/auth/verify` on that host exchanges the code for a **per-app session** `app-sess:{sid2}` valid only for that slug, then sets `__Host-portal_app_sid`. A stolen app cookie is then worth one app, not the portal. `/auth/verify`, minting and the SDK are unchanged apart from where the cookie comes from. Not built in Phases 1–3.

## 13. Failure modes

| Failure | Behaviour | Detection | Recovery |
|---|---|---|---|
| Redis down | `/auth/verify` → 503 (fail closed), pages show maintenance | `/readyz`, `redis_unavailable` | restart Redis; users re-login (sessions lost by design, R7) |
| IdP down | existing sessions unaffected; `/login` shows "Anmeldung derzeit nicht möglich" | `login_failure{token_endpoint}` | wait; contact IdP owner |
| Registry DB unreadable | snapshot in memory keeps serving; `/readyz` fails; registry writes rejected | `/readyz` | restore latest backup (`03` §10) |
| Signing key missing at start | gateway refuses to start | container exit, `key_loaded` absent | regenerate / restore secret |
| Clock skew > leeway | ID-token validation fails | `login_failure{exp}` | fix NTP on the VM |
| Traefik cannot reach gateway | all `/apps/*` denied | Traefik healthcheck, Playwright smoke | restart gateway |
| Memory growth (mint cache) | bounded LRU, 10 000 entries | — | none needed |

## 14. Tests

| # | Case |
|---|---|
| G1 | `next=//evil.example`, `next=/\evil`, `next=https://evil`, `next=/apps/..%2f..` → all sanitized to `/` |
| G2 | Callback without `__Host-portal_login` cookie → 400, no session created |
| G3 | Callback with valid `state` but a different browser's `lid` → 400 |
| G4 | Replayed callback (same code twice) → second fails, `oidc:{lid}` already consumed |
| G5 | ID token with wrong `iss`, wrong `aud`, expired, wrong `nonce`, `alg=none`, HS256 → each rejected with the right internal reason, identical user-facing page |
| G6 | New session id differs from any pre-login cookie value (fixation) |
| G7 | `/auth/verify` decision table: one test per row of §6, including ordering (unauthorized user on an unhealthy app → 403, not 503) |
| G8 | Slug extraction: `/apps/noten`, `/apps/noten/`, `/apps/noten/x`, `/apps/notenfoo/`, `/apps/NOTEN/`, `/apps/n/` → expected slug or 404 |
| G9 | CSRF: POST with `Sec-Fetch-Site: cross-site` → 403; same-origin → pass; curl (no headers) → pass |
| G10 | `Origin: https://evil` on POST → 403 |
| G11 | H5 enabled: fetch from `/apps/a/` page to `/apps/b/api` → 403; app b's own fetch → pass; top-level navigation → pass |
| G12 | Idle expiry: no request for 31 min → 302; request every 29 min for 8 h 01 min → forced re-login |
| G13 | `touch` writes to Redis at most once per minute under 100 requests/s |
| G14 | Mint cache: 50 requests, one slug, one session → 1 signature; after logout the next request re-mints (and is denied) |
| G15 | Assertion carries exactly the claims in §7; no `email` unless declared; `aud` has `adapters` only when scopes exist |
| G16 | JWKS lists current only; with `next` and `previous` files present lists all three; each `kid` equals the key's RFC 7638 thumbprint |
| G17 | Rotation script: SDK fixtures signed with the old key still verify during steps 1–4 |
| G18 | Redis killed mid-request → 503, no 200 under any path |
| G19 | Peer outside `172.29.10.0/29` calling `/auth/verify` or `/registry/*` → 403 |
| G20 | Bind check: connecting to `172.29.11.2:8000` from an `apps` container is refused |
| G21 | `revoke-sessions --sub` removes all sessions; next request → login |
| G22 | Role mapping: worked example in §8 yields `{employee, pilot-tester}`; unmapped user → empty roles, empty menu, every app 403 |
| G23 | Log scan: no cookie, assertion or token substring appears in any log line across the E2E run |
| G24 | Config validation: unknown key, missing file, non-local listen address → startup error naming the problem |
| G25 | Keycloak (stage) end-to-end: three users in three roles log in and see exactly their menus |

## 15. Open points

- IdP attribute release and claim names (`02-open-questions.md` §1): the `roles.yml` source claims above are placeholders until the new Shibboleth is specified.
- `private_key_jwt` vs `client_secret_basic`: ask the Shibboleth team what the new OP supports.
- Whether `amr` should become an enforced requirement for sensitive apps (step-up, `02` §1) — not in the pilot.
- Static IPs in §1 must be checked against HKA's network ranges (`README.md`, open decision).
