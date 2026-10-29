# 06 — Portal SDK (Python and JavaScript)

Implementation-level specification. Overview: `../09-component-design.md` §6. The SDK is the **only** code in an app that reads identity, builds page chrome, or calls a legacy system. It exists in two implementations from one specification and one shared fixture set. ⚑ = confirm at implementation.

## 1. Design constraints

| Constraint | Consequence |
|---|---|
| Authors are laypeople plus an AI | Few concepts, fail-closed defaults, errors in plain language |
| Two languages must behave identically | One spec (this file), one fixture catalogue (§9), one client generator (§8) |
| SDK is vendored into every starter (R9) | Small (target ≤ 600 lines per language), minimal dependencies, no build step |
| Works offline in the DevContainer | Dev shim and in-SDK adapter fixtures (§7) |
| Must not be removable without detection | Hash check (§10) and the deploy-time conformance probe (`09-pipeline-and-deploy.md`) |

Runtimes: Python 3.12 / FastAPI (Starlette ASGI) ≥ 0.115 ⚑; Node 24 LTS / Express 5 ⚑. Dependencies — Python: `PyJWT[crypto]`, `httpx`, `pydantic` (already in FastAPI). JavaScript: `jose` only (built-in `fetch`).

## 2. Environment variables

| Variable | Default (dev) | Production value (set by the compose template) | Purpose |
|---|---|---|---|
| `PORTAL_ENV` | `development` | `production` | **`production` forbids dev mode** |
| `PORTAL_SLUG` | from `manifest.json` | slug | `aud` check, logging |
| `PORTAL_BASE_PATH` | *(empty)* | `/apps/<slug>` | prefix for routes and links; empty under future host routing |
| `PORTAL_API_URL` | `http://portal-api:8001` | same | JWKS and nav |
| `PORTAL_ADAPTERS_URL` | `http://portal-adapters:8002` | same | adapter client base |
| `PORTAL_ISSUER` | `https://portal.hka.example/` | from environment | expected `iss` |
| `PORTAL_DEV` | `1` in the DevContainer | *(unset)* | enable dev shim |
| `PORT` | `8080` | `8080` | listen port (fixed convention) |
| `LOG_LEVEL` | `INFO` | `INFO` | |

Anything else an app needs (its own settings, `APP_SECRET_*`) is its own business and arrives through the normal environment.

## 3. Public API

### 3.1 Python

```python
# platform_sdk/__init__.py (signatures; behaviour in §4–§7)
from dataclasses import dataclass

@dataclass(frozen=True)
class User:
    sub: str
    name: str
    roles: tuple[str, ...]
    email: str | None = None

class Portal:
    @classmethod
    def from_env(cls, manifest_path: str = "manifest.json") -> "Portal": ...
    base_path: str                      # "" or "/apps/<slug>"
    manifest: dict

    def install(self, app: "FastAPI") -> None: ...        # middleware + /healthz (+ dev shim when enabled)
    def router(self, **kw) -> "APIRouter": ...            # APIRouter(prefix=self.base_path, **kw)
    def user(self, request: "Request") -> User: ...        # FastAPI dependency; raises 401 if absent
    def requires(self, *roles: str): ...                   # dependency factory; 403 if none of roles
    def url(self, path: str) -> str: ...                   # base_path + path (never build links by hand)
    async def layout(self, *, title: str, body: str, current: str, user: User) -> str: ...
    adapters: "Adapters"                                    # generated, §8

class AdapterError(Exception):
    status: int; type: str; detail: str; request_id: str | None
```
Typical use (this is what the starter's `src/app/main.py` contains):
```python
portal = Portal.from_env()
app = FastAPI()
portal.install(app)
router = portal.router()

@router.get("/", response_class=HTMLResponse)
async def home(user: User = Depends(portal.user)):
    grades = await portal.adapters.noten.list_my_grades()
    return await portal.layout(title="Meine Noten", body=render_grades(grades), current=portal.url("/"), user=user)

app.include_router(router)
```

### 3.2 JavaScript

```js
// platform_sdk/index.js (signatures)
export class Portal {
  static fromEnv({ manifestPath = "manifest.json" } = {}) {}
  basePath;                 // "" or "/apps/<slug>"
  manifest;
  install(app) {}           // Express 5: verification middleware + /healthz (+ dev shim)
  router() {}               // express.Router(); mount with app.use(portal.basePath || "/", router)
  requires(...roles) {}     // middleware; 403 if none of roles
  url(path) {}              // basePath + path
  async layout({ title, body, current, user }) {}   // returns an HTML string
  adapters;                 // generated, §8
  // inside handlers: req.portal.user -> { sub, name, roles, email? }
}
export class AdapterError extends Error { status; type; detail; requestId; }
```
```js
const portal = Portal.fromEnv();
const app = express();
portal.install(app);
const router = portal.router();
router.get("/", async (req, res) => {
  const grades = await portal.adapters.noten.listMyGrades(req);
  res.type("html").send(await portal.layout({ title: "Meine Noten", body: renderGrades(grades), current: portal.url("/"), user: req.portal.user }));
});
app.use(portal.basePath || "/", router);
app.listen(8080);
```
(In Node the adapter client takes `req` to find the assertion; in Python it reads a context variable set by the middleware. Same behaviour, idiomatic wiring.)

## 4. Request verification

`install()` adds middleware that runs **before** every route.

```text
handle(request):
  if path == "/healthz":                      -> pass through, no verification (GET/HEAD only)
  if dev_mode and path startswith "/__dev/":  -> dev shim handlers (§7)
  token := header "X-Portal-Assertion"
  if dev_mode and token is None:              user := dev_user_from_cookie(request)  (else redirect to /__dev/login)
  else:
      if token is None -> 401
      claims := verify(token, expected_aud = PORTAL_SLUG)     # §5; any failure -> 401
      user   := User(claims.sub, claims.name, claims.roles, claims.email)
      remember raw token in request context for adapter calls
  set request context user
  continue
401 response: text/html page "Anmeldung fehlt" when Accept has text/html, else application/problem+json.
```
**Fail-closed:** a route without an explicit exemption is protected. The only exemption is `/healthz`. An app cannot register another public route through the SDK; code that bypasses `install()` is caught by the conformance probe.

`requires(*roles)`: 403 problem/page if `set(user.roles) ∩ set(roles) = ∅`. It is a second line of defence, not the primary one (the gateway already checked the manifest roles).

## 5. Assertion verification (`verify(token, now=None)`)

```text
verify(token, expected_aud, now):
  if len(token) > 8192 or token.count(".") != 2           -> Malformed
  header := decode_header(token)                          # no signature check yet
  if header.alg != "RS256"                                -> BadAlgorithm   # rejects none, HS*, ES*
  if not header.kid                                       -> MissingKid
  key := jwks.get(header.kid)                             # §6 ; unknown kid -> UnknownKey
  claims := decode_and_verify_signature(token, key, algorithms=["RS256"])   # reject on bad signature
  require claims.iss == PORTAL_ISSUER                     -> WrongIssuer
  require expected_aud ∈ aslist(claims.aud)               -> WrongAudience
  require claims.v == 1                                   -> UnsupportedVersion
  require claims.exp >= now - 5 and claims.iat <= now + 5 -> Expired / NotYetValid     # 5 s leeway
  require non-empty string claims.sub                     -> MissingSubject
  require claims.roles is a list of strings               -> BadRoles
  ignore unknown extra claims
  return claims
```
Errors never echo token content. `now` is injectable so the shared fixtures are deterministic (§9).

## 6. JWKS cache

```text
state: keys{kid -> public key}, fetched_at, last_unknown_refetch
get(kid):
  if kid in keys and now - fetched_at < 300 s: return keys[kid]          # fresh
  if kid not in keys and now - last_unknown_refetch >= 30 s:             # rotation / first use; rate-limited
        refetch() ; last_unknown_refetch := now
  elif kid in keys and now - fetched_at >= 300 s:
        refetch()                                                          # background refresh
  if kid in keys: return keys[kid]        # stale-if-error: usable for up to 1 h after fetched_at
  raise UnknownKey
refetch(): GET PORTAL_API_URL/.well-known/jwks.json, timeout 2 s; on failure keep old keys, log once per minute
```
Thundering herd: concurrent first requests share one in-flight fetch. Startup: the SDK prefetches once and logs a warning (not an error) if the gateway is unreachable, so an app can start before the platform.

## 7. Dev shim and dev adapters

Enabled only if `PORTAL_DEV=1` **and** `PORTAL_ENV != production` **and** `PORTAL_BASE_PATH` is empty. If `PORTAL_DEV` is set while either other condition is violated the SDK **raises at startup** ("Der Entwicklungsmodus darf nicht in Produktion laufen."). The pipeline additionally fails if the string `PORTAL_DEV` appears in the production compose output or image environment.

- `GET /__dev/login`: simple form — display name, checkboxes for every role in `manifest.roles` plus free text for extra roles. `POST` sets cookie `portal_dev` = base64(JSON user) + HMAC (key random per process, `HttpOnly`, `SameSite=Lax`) and redirects to `/`.
- The middleware turns the cookie into a `User` exactly as production does from claims, so `requires()` and templates behave identically.
- **Adapters in dev** use an in-process mock transport serving the same fixture JSON as the adapter service's `mock` backend (copied into `platform_sdk/fixtures/` at SDK release). Authors get realistic data without any network. `PORTAL_ADAPTERS_URL` set explicitly overrides this (to test against a local adapter container).
- `layout()` in dev renders a static nav built from the app's own manifest plus a sample menu, with the kit CSS bundled in the SDK at `/__dev/kit.css` so the page looks like production.
- A dev banner ("Entwicklungsmodus – Testperson: {name}") is injected into `layout()` output so screenshots cannot be mistaken for production.

## 8. Adapter client

Generated from the three OpenAPI files by **one generator** (`tools/gen_clients.py`), producing `platform_sdk/adapters/` for Python and JavaScript. Generated output is committed, never hand-edited; CI regenerates and fails on a diff.

```python
# generated shape (Python)
class NotenClient:
    async def list_my_grades(self, *, semester: str | None = None) -> GradeList: ...
class MailClient:
    async def send_message(self, *, to: list[str], subject: str, text: str, idempotency_key: str | None = None) -> Accepted: ...
    async def list_inbox(self, *, limit: int = 20) -> InboxList: ...
```
Behaviour (both languages):
- Base URL `PORTAL_ADAPTERS_URL`; header `Authorization: Bearer <assertion of the current request>`; no assertion in context (e.g. called at startup) → `AdapterError(type="no-user-context")`.
- Timeout 8 s (adapter upstream limit is 5 s); **no automatic retries** (the adapter handles idempotency; blind retries of a send are a bug source). GETs may be retried once by the caller.
- Response bodies validated against the generated models; an unexpected shape raises `AdapterError(type="contract-violation")` — better a clear error than a silent wrong table.
- Problem responses become `AdapterError` carrying `status`, `type`, safe German `detail`, `request_id`; apps may display `detail` directly.
- `send_message` generates an `Idempotency-Key` (UUIDv4) if the caller gave none, and reuses it if the **same call object** is repeated.
- Models are strict (`extra="forbid"` in pydantic; explicit field copying in JS) to mirror `additionalProperties: false`.

## 9. Shared fixture catalogue (parity guarantee)

`sdk-fixtures/` is a directory of JSON files consumed by **both** SDKs' test suites. A fixed RSA test key pair (`test_private.pem` is used only by the fixture generator; `jwks.json` is shipped) signs the tokens once; tokens, the injected `now`, and the expected outcome are stored, so results are deterministic and identical across languages.

```json
{
  "name": "expired-beyond-leeway",
  "now": 1792924900,
  "expected_aud": "noten",
  "token": "<compact JWT, exp = 1792924860 (40 s before now)>",
  "expect": { "ok": false, "error": "Expired" }
}
```

| # | Fixture | Expectation |
|---|---|---|
| F1 | `valid` — aud `[noten, portal, adapters]`, roles `[student]` | ok; claims returned |
| F2 | `valid-with-email` | ok; `email` present |
| F3 | `valid-aud-string` — `aud: "noten"` | ok |
| F4 | `within-leeway` — `exp` 3 s before `now` | ok |
| F5 | `expired-beyond-leeway` — `exp` 40 s before `now` | `Expired` |
| F6 | `not-yet-valid` — `iat` 30 s after `now` | `NotYetValid` |
| F7 | `wrong-audience` — aud `[other, portal]` | `WrongAudience` |
| F8 | `wrong-issuer` | `WrongIssuer` |
| F9 | `alg-none` (unsigned) | `BadAlgorithm` |
| F10 | `alg-hs256-public-key-as-secret` (key-confusion attack) | `BadAlgorithm` |
| F11 | `alg-es256` signed with a valid EC key | `BadAlgorithm` |
| F12 | `tampered-payload` (roles changed, signature kept) | `BadSignature` |
| F13 | `tampered-signature` | `BadSignature` |
| F14 | `unknown-kid` | `UnknownKey` |
| F15 | `missing-kid` | `MissingKid` |
| F16 | `kid-previous-key` — signed by a key listed as `previous` in the fixture JWKS | ok |
| F17 | `version-2` — `v: 2` | `UnsupportedVersion` |
| F18 | `roles-not-a-list` — `roles: "student"` | `BadRoles` |
| F19 | `empty-sub` | `MissingSubject` |
| F20 | `extra-claim` — unknown claim `foo` | ok; claim ignored |
| F21 | `oversize` — 9 000 bytes | `Malformed` |
| F22 | `three-parts-garbage`, `two-parts`, `empty-string` | `Malformed` |

Additional shared behavioural cases (each language implements them against its own web framework): missing header → 401; valid header → handler sees `user`; `/healthz` without header → 200; `requires("student")` with roles `[employee]` → 403; dev shim refused when `PORTAL_ENV=production`; `layout()` fallback when the nav fetch fails; adapter 403 problem → `AdapterError.type == "scope-not-granted"`.

## 10. Vendoring, release manifest and hash check (R9)

Layout inside a starter:
```
platform_sdk/            # Python:  platform_sdk/{__init__,config,verify,jwks,middleware,layout,nav,devshim,healthcheck,verify_tree,errors}.py
├── VERSION              #          adapters/{__init__,models,clients}.py   fixtures/*.json   templates/layout.html
└── …                    # JS:      same names as .js ES modules
```
Release manifest `sdk-releases.json` (in the platform repo, protected branch):
```json
{
  "1.0.0": { "python": "sha256:<hash>", "javascript": "sha256:<hash>", "assertion_versions": [1], "released": "2026-11-12" }
}
```
`verify_tree` (shipped inside the SDK for fast local feedback; the **authoritative** copy is the central pipeline's own `sdk_verify`, because a tool inside the tree it checks can be altered together with it) computes `sha256` over the sorted list of `(relative path, file bytes)` for all files below `platform_sdk/` (excluding `__pycache__`, `node_modules`) and compares with the entry for `platform_sdk/VERSION`:
- run by `make lint` (early feedback) and by the pipeline's **lint stage** (authoritative; the check script is central, the manifest is fetched from the platform repo at the pinned pipeline version);
- mismatch → pipeline error `PF-103` (`09-pipeline-and-deploy.md` §6): "Die Portal-Bibliothek wurde verändert."
- `make sdk-update [VERSION]` replaces the directory with the released copy (fetched from the platform repo) and updates `VERSION`.

What the hash check does **not** cover: an author who never calls `install()`. That is the conformance probe's job: such an app returns 200 to a request without an assertion and is rejected at deploy.

## 11. Logging

JSON lines to stdout: `{"ts","level","event","request_id","user_hash","path","status","ms"}`. `request_id` comes from the `X-Request-Id` header set by the gateway. `user_hash` = first 12 hex of SHA-256 over `sub` (apps have no HMAC key; this is for correlation inside one app's logs only). **Never logged:** the assertion, claim values other than the hash, adapter response bodies.

## 12. Compatibility and versioning

| Axis | Rule |
|---|---|
| SDK ↔ assertion | SDK 1.x accepts `v: 1` only. A future `v: 2` is introduced by minting both versions for a transition window announced in release notes. |
| SDK ↔ adapters | generated clients target `/v1`; a `/v2` appears as SDK 2.x |
| SDK ↔ kit | `layout.html` references kit CSS/JS by hashed names delivered via the nav response header `X-Portal-Kit` (`04` §8); a kit **major** change ships with an SDK major |
| Semver | patch = bug fix, minor = additive API, major = breaking. Starters pin an exact version; `make sdk-update` is explicit. |
| Runtime | Python 3.12, Node 24 LTS; moving to the next LTS is a minor release of the SDK and a new starter base image |

## 13. Tests (SDK repo CI, both languages)

| # | Case |
|---|---|
| S1 | All fixtures F1–F22 produce the expected result in Python **and** JavaScript (single table-driven test per language reading the same files) |
| S2 | Parity job: runs both test suites and diffs their per-fixture result lists; any difference fails |
| S3 | Middleware: protected route without header → 401; with header → 200 and correct `user`; `/healthz` open |
| S4 | JWKS: unknown `kid` triggers one refetch; 100 concurrent requests with unknown `kid` → one fetch; second unknown `kid` within 30 s → no fetch |
| S5 | JWKS stale-if-error: gateway down, cached key younger than 1 h → verification succeeds; older → `UnknownKey` |
| S6 | `layout()`: valid HTML (parsed), contains skip link, `lang="de"`, nav fragment, kit link; nav fetch failure → minimal nav + logged warning, status 200 |
| S7 | Nav cache: second call within 60 s makes no request; after expiry sends `If-None-Match`; 304 reuses body |
| S8 | Dev shim: refused at startup under `PORTAL_ENV=production`; login form sets cookie; `requires()` honours dev roles; dev banner present |
| S9 | Adapter client: sets bearer from context; maps each problem type; contract-violation on an extra field; no retry on 5xx POST; idempotency key reused for the same call |
| S10 | Generator: regenerating from the OpenAPI files yields no diff |
| S11 | `sdk_verify`: pristine tree passes; one changed byte, one added file, one deleted file → fail |
| S12 | Size budget: each implementation ≤ 600 lines (excluding generated clients and fixtures) — a soft check that warns |
| S13 | Log scan: no assertion or claim value appears in logs during the whole suite |

## 14. Open points

- Express 5 and FastAPI version pins (⚑) at implementation.
- Whether the SDK should also expose a typed `manifest` helper for apps that render their own settings screen (not needed for the reference apps).
- Distribution after the 28.10 Git decision: stay vendored or add the platform's package registry (`../09-component-design.md` §14 item 3); the hash-manifest scheme works for both.
