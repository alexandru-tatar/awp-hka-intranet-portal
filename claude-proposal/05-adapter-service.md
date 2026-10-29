# 05 — Adapter Service

Implementation-level specification. Overview: `../09-component-design.md` §5. The adapters are the **only** path from an app to Mail/Exchange, Noten and E-Akte (skill `schnittstellen`; scoping of this rule: `../03-proposal-review.md` finding 12). Names and ports: `README.md`. ⚑ = confirm at implementation.

## 1. Purpose and boundaries

- Translate a small, stable, documented HTTP API into the legacy systems' protocols.
- Authenticate every call with the **assertion** (`../09-component-design.md` §0.3) and enforce, per call: the app's declared scope (`scp`), the user's role policy, and "acts only as `sub`".
- Hold legacy credentials. **No app ever receives one** (`../09-component-design.md` §5.4).
- Provide three interchangeable backends per system (`mock | stage | live`) so apps and tests behave identically across environments (AF-15 plugs in at `stage`).

Not in scope: scheduling/background jobs (impossible by construction, a pilot limit), caching of personal data, any write path beyond "send mail".

| Property | Value |
|---|---|
| Stack | Python 3.12, FastAPI, uvicorn (1 worker), httpx, PyJWT, pydantic v2, PyYAML |
| Network | `apps` (172.29.11.3:8002), `egress` (172.29.13.3; legacy hosts only, host-firewalled allow-list) |
| FS | uid 10002, `read_only: true`; writable `/var/lib/portal/audit` (volume), `/tmp` |
| Public contract | OpenAPI 3.1 files in `adapters/openapi/{noten,mail,eakte}.yaml` (contract #3) |

## 2. Request pipeline

```text
request
  1. parse Authorization: Bearer <assertion>            -> 401 problem "unauthenticated" if absent
  2. verify (alg RS256, kid via JWKS from portal-api:8001, iss, exp/iat ±5 s, aud ∋ "adapters")
                                                        -> 401 "assertion-invalid"
  3. route scope S := openapi `x-required-scope` of the operation      (e.g. "noten:read")
     require S ∈ assertion.scp                          -> 403 "scope-not-granted"
  4. role policy P := policy.yml[system]                  (e.g. noten: allow roles [student])
     require roles(assertion) ∩ P.allow ≠ ∅            -> 403 "role-not-allowed"
  5. rate limit key (azp, sub) per operation class      -> 429 "rate-limited" + Retry-After
  6. idempotency (POST only, header Idempotency-Key)    -> replay stored response if key seen
  7. backend call with user := assertion.sub only        timeouts, breaker (§7)
  8. audit line (§9) — also for denials at steps 3–5
  9. respond (problem+json on error)
```
Invariants: the adapter never reads a user identifier from the request body, path or query; there is no parameter that selects another user (so there is nothing to forge). Assertions are never logged or forwarded to backends.

## 3. Problem types

All errors: `Content-Type: application/problem+json`, body `{type, title, status, detail, request_id}`; `detail` is German, short, safe to show.

| `type` | Status | Meaning | Example `detail` |
|---|---|---|---|
| `urn:hka:problem:unauthenticated` | 401 | no bearer token | "Anmeldung fehlt." |
| `urn:hka:problem:assertion-invalid` | 401 | bad signature, expired, wrong `aud`/`iss` | "Anmeldung ist ungültig oder abgelaufen." |
| `urn:hka:problem:scope-not-granted` | 403 | app did not declare the scope | "Diese Anwendung darf auf Noten nicht zugreifen." |
| `urn:hka:problem:role-not-allowed` | 403 | user's roles not allowed for the system | "Für Ihre Rolle ist dieser Dienst nicht freigegeben." |
| `urn:hka:problem:validation` | 422 | malformed body (lists JSON pointers) | "Bitte prüfen Sie Ihre Eingaben." |
| `urn:hka:problem:recipient-not-allowed` | 422 | mail recipient outside the allow-list (§6) | "Diese Empfängeradresse ist nicht erlaubt." |
| `urn:hka:problem:rate-limited` | 429 | token bucket empty | "Zu viele Anfragen. Bitte warten Sie kurz." |
| `urn:hka:problem:backend-unavailable` | 503 | breaker open / connect failure | "Das System ist gerade nicht erreichbar." |
| `urn:hka:problem:backend-timeout` | 504 | upstream exceeded 5 s | "Das System antwortet zu langsam." |
| `urn:hka:problem:not-implemented` | 501 | operation exists in the contract but the active backend lacks it | "Diese Funktion ist hier noch nicht verfügbar." |

## 4. Contract excerpts (contract #3)

### 4.1 `noten.yaml`

```yaml
openapi: 3.1.0
info: { title: HKA Portal — Noten-Adapter, version: 1.0.0 }
servers: [ { url: "http://portal-adapters:8002" } ]
security: [ { portalAssertion: [] } ]
paths:
  /v1/noten/me/grades:
    get:
      operationId: listMyGrades
      summary: Noten der angemeldeten Person (nur lesen)
      x-required-scope: "noten:read"
      x-allowed-roles: [student]
      parameters:
        - { name: semester, in: query, required: false, schema: { type: string, pattern: "^(WS|SS) \\d{4}(/\\d{2})?$" } }
      responses:
        "200":
          description: Liste der Noten
          content:
            application/json:
              schema: { $ref: "#/components/schemas/GradeList" }
        "403": { $ref: "#/components/responses/Problem" }
        "503": { $ref: "#/components/responses/Problem" }
components:
  securitySchemes:
    portalAssertion: { type: http, scheme: bearer, bearerFormat: JWT }
  responses:
    Problem:
      description: Fehler
      content:
        application/problem+json:
          schema: { $ref: "#/components/schemas/Problem" }
  schemas:
    Grade:
      type: object
      additionalProperties: false
      required: [module, semester, grade]
      properties:
        module:   { type: string, maxLength: 120, examples: ["Mathematik 1"] }
        semester: { type: string, examples: ["WS 2025/26"] }
        grade:    { type: string, pattern: "^([1-4][,.][037]|5[,.]0|bestanden|nicht bestanden)$", examples: ["2,3"] }
        credits:  { type: integer, minimum: 0, maximum: 30 }
    GradeList:
      type: object
      additionalProperties: false
      required: [items]
      properties:
        items: { type: array, maxItems: 500, items: { $ref: "#/components/schemas/Grade" } }
    Problem:
      type: object
      required: [type, title, status, request_id]
      properties:
        type: { type: string }
        title: { type: string }
        status: { type: integer }
        detail: { type: string }
        request_id: { type: string }
```

### 4.2 `mail.yaml`

```yaml
openapi: 3.1.0
info: { title: HKA Portal — Mail-Adapter, version: 1.0.0 }
servers: [ { url: "http://portal-adapters:8002" } ]
security: [ { portalAssertion: [] } ]
paths:
  /v1/mail/messages:
    post:
      operationId: sendMessage
      summary: "Nachricht senden (Absender: gemeinsames Funktionskonto)"
      x-required-scope: "mail:send"
      x-allowed-roles: [employee, professor]
      parameters:
        - { name: Idempotency-Key, in: header, required: true, schema: { type: string, minLength: 16, maxLength: 64 } }
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: "#/components/schemas/OutgoingMessage" }
      responses:
        "202": { description: Zur Zustellung angenommen, content: { application/json: { schema: { $ref: "#/components/schemas/Accepted" } } } }
        "422": { $ref: "#/components/responses/Problem" }
        "429": { $ref: "#/components/responses/Problem" }
  /v1/mail/inbox:
    get:
      operationId: listInbox
      summary: "Posteingang der angemeldeten Person (nur Betreff und Absender, nichts wird gespeichert)"
      x-required-scope: "mail:read"
      x-allowed-roles: [employee, professor]
      parameters:
        - { name: limit, in: query, schema: { type: integer, minimum: 1, maximum: 50, default: 20 } }
      responses:
        "200": { description: Kopfdaten, content: { application/json: { schema: { $ref: "#/components/schemas/InboxList" } } } }
        "501": { $ref: "#/components/responses/Problem" }
components:
  securitySchemes:
    portalAssertion: { type: http, scheme: bearer, bearerFormat: JWT }
  responses:
    Problem:
      description: Fehler
      content: { application/problem+json: { schema: { type: object } } }
  schemas:
    OutgoingMessage:
      type: object
      additionalProperties: false
      required: [to, subject, text]
      properties:
        to:      { type: array, minItems: 1, maxItems: 5, items: { type: string, format: email, maxLength: 254 } }
        subject: { type: string, minLength: 1, maxLength: 120 }
        text:    { type: string, minLength: 1, maxLength: 5000, description: "Nur Klartext; HTML wird nicht angenommen." }
    Accepted:
      type: object
      required: [id]
      properties: { id: { type: string } }
    InboxList:
      type: object
      required: [items]
      properties:
        items:
          type: array
          items:
            type: object
            required: [from, subject, received]
            properties:
              from: { type: string }
              subject: { type: string }
              received: { type: string, format: date-time }
```

### 4.3 `eakte.yaml` (stub until an API path is confirmed)

One operation, `GET /v1/eakte/me/documents` (`x-required-scope: eakte:read`), returning `{items:[{title, type, updated}]}`; implemented only by the `mock` backend; `stage`/`live` answer `501 not-implemented`. Purpose: let the `schnittstellen` skill and the AI know the shape without inventing it (`../04-umgebung-und-prompts.md`: "damit sie keine Adresse oder kein Feld erfindet").

### 4.4 Contract rules

- Additive changes within `/v1` only; a breaking change is `/v2`, both served for one release (`02-open-questions.md` §5 default: apps pin a version via the generated client).
- `additionalProperties: false` on every request and response object so drift is a test failure, not a surprise.
- Every operation carries `x-required-scope` and `x-allowed-roles`; the **manifest check** in the pipeline reads `x-required-scope` values to know which `adapters` entries are legal (`03-registry.md` §3).

## 5. Configuration — `adapters.yml`

```yaml
env: prod
listen: { host: 172.29.11.3, port: 8002 }
jwks_url: http://portal-api:8001/.well-known/jwks.json
assertion: { issuer: https://portal.hka.example/, leeway_seconds: 5 }

audit:
  dir: /var/lib/portal/audit
  hmac_key_file: /run/secrets/audit_hmac_key

limits:
  default:       { per_user_per_minute: 60 }
  mail_send:     { per_user_per_hour: 20, per_user_per_day: 100 }
  mail_inbox:    { per_user_per_minute: 12 }
  breaker:       { failures: 5, window_seconds: 30, open_seconds: 30 }
  upstream_timeout_seconds: 5

policy:
  noten:  { allow_roles: [student] }
  mail:   { allow_roles: [employee, professor] }
  eakte:  { allow_roles: [employee] }

backends:
  noten:  { mode: mock }                    # mock | stage | live
  mail:   { mode: mock }
  eakte:  { mode: mock }

mail:
  sender: no-reply@hka.example              # shared functional account (02-open-questions §5 default)
  recipient_domains_allow: [hka.example]    # prod; stage uses explicit test addresses (§6)
  stage_recipient_allow: ["^[a-z0-9._-]+@test\\.hka\\.example$"]
  max_recipients: 5
```
Modes per environment: **dev** all `mock`; **stage** `mock` → `stage` per system as datasets arrive; **prod** `live` once the client delivers test interfaces (26.11) and the credential strategy is decided.

## 6. Backends

```python
# adapters/backends/noten.py — interface (illustrative; signatures are the contract between layers)
class NotenBackend(Protocol):
    async def grades(self, sub: str, semester: str | None) -> list[Grade]: ...
```
| Implementation | Source of data | Notes |
|---|---|---|
| `MockNoten` | `fixtures/noten/<sub>.json`; unknown `sub` → empty list | Test users `student-test`, `student-empty`; deterministic |
| `StageNoten` | anonymised dataset provisioned by the "Infrastrukturanbieter" role (AF-15) | exact interface (DB view vs HTTP) is agreed with whoever provisions it; the adapter only needs `grades(sub)` |
| `LiveNoten` | the Noten system's interface (to be delivered by HKA, §8.1 26.11) | uses a credential strategy below |

**Credential strategies** (per system, config key `auth: service_account | impersonation | user_password`):
- `service_account` — API credential held as a Docker secret `adapter_<system>_credential`; preferred.
- `impersonation` — e.g. Exchange application impersonation; no user password anywhere. **First question for the Exchange admin.**
- `user_password` — the client's split-secret sketch: password entered once on `/_portal/connections`, encrypted under `HKDF(server_half ‖ session_half)`; server half in a secret, session half in the user's Redis session; unusable after the session ends. Design only, behind the same interface.

Until a strategy is confirmed, `mail` and `eakte` stay `mock` (`../02-open-questions.md` §5: stub until an API path is confirmed).

### 6.1 Mail abuse controls (R16)

A shared no-reply account plus an AI-built app is a potential phishing relay under the HKA name. Controls, all enforced in the adapter (never in the app):

1. `to` ≤ 5 addresses; each must match `recipient_domains_allow` in prod, or `stage_recipient_allow` regexes in stage.
2. Plain text only (`text` field); no HTML, no attachments, no custom headers; subject ≤ 120 characters.
3. Per-user caps: 20/hour and 100/day (`limits.mail_send`); exceeding → 429 and an audit line.
4. `From` is always `mail.sender`; the visible footer line "Gesendet über das HKA Portal im Auftrag von {name}" is appended by the adapter (so recipients can see it is not a personal address). `Reply-To` is the user's email **only if** the app declared the `email` claim in its manifest.
5. `Idempotency-Key` required; the same key within 24 h returns the first response without sending again.
6. Every send is audited (no body, no recipient list — only count and domains).

## 7. Reliability

| Mechanism | Parameters |
|---|---|
| Timeout | 5 s per upstream call (connect 2 s) |
| Retries | none for non-idempotent calls; one retry for idempotent GETs on connect errors |
| Circuit breaker | per backend: opens after 5 failures within 30 s, stays open 30 s, then one trial call (half-open) |
| Rate limits | token buckets in memory, key `(azp, sub, operation class)`; restart resets them (acceptable, documented) |
| Idempotency | SQLite file `/var/lib/portal/audit/idem.db`: `(key, azp, sub, status, response_json, created)`; rows pruned after 24 h; key is scoped to `(azp, sub)` so one user cannot replay another's key |
| Backpressure | bounded semaphore of 16 concurrent upstream calls; excess → 503 `backend-unavailable` |

## 8. Health

- `GET /healthz` — process alive.
- `GET /readyz` — JWKS fetched at least once, audit directory writable, every configured backend constructed. Backend *reachability* is deliberately **not** part of readiness (a down legacy system must not make Compose restart the adapter); it appears in `GET /v1/status` (assertion with role `platform-admin`): per backend `mode`, breaker state, last success.

## 9. Audit

Append-only JSON lines, one file per month, `/var/lib/portal/audit/adapter-YYYY-MM.jsonl`, mode 0640. **No payloads, no message text, no recipient addresses.**

```jsonl
{"ts":"2026-11-19T10:12:03.412Z","request_id":"r-8f2c","azp":"noten","sub_hash":"3b9f0c2a41d7e6a1","system":"noten","op":"listMyGrades","status":200,"ms":84,"decision":"allow"}
{"ts":"2026-11-19T10:12:41.007Z","request_id":"r-8f2d","azp":"nachricht","sub_hash":"91aa07c4be02d533","system":"mail","op":"sendMessage","status":429,"ms":1,"decision":"deny:rate"}
```
`sub_hash` = first 16 hex of `HMAC-SHA256(audit_hmac_key, sub)` (R19): events of one person correlate, the person cannot be read from the file. Denials from steps 3–5 are audited too. Retention is an open data-protection decision (`../09-component-design.md` §14 item 7; `02-open-questions.md` §11 suggests 30 days for logs).

## 10. Directory layout

```
adapters/
├── openapi/{noten,mail,eakte}.yaml
├── src/portal_adapters/
│   ├── app.py            # FastAPI factory, routers, problem handlers
│   ├── auth.py           # assertion verification + JWKS cache
│   ├── policy.py         # scope + role checks from OpenAPI vendor extensions and policy.yml
│   ├── limits.py         # token buckets, breaker, semaphore
│   ├── idempotency.py
│   ├── audit.py
│   └── backends/{noten,mail,eakte}/{base.py,mock.py,stage.py,live.py}
├── fixtures/{noten,mail,eakte}/
├── tests/
├── policy.yml  adapters.yml
└── Dockerfile
```
The OpenAPI files are the single source for: server request validation, the generated types in both SDKs (`06-portal-sdk.md`), the manifest check's list of legal scopes, and the `schnittstellen` skill's reference text.

## 11. Contract-test matrix

The same suite (`tests/contract/`) runs against every backend mode that exists for a system; a mock that drifts from `stage` fails CI.

| Case | `mock` | `stage` |
|---|---|---|
| Student with grades → items match schema (additionalProperties false) | ✔ | ✔ |
| Student without grades → `items: []` | ✔ | ✔ |
| `semester` filter returns only that semester | ✔ | ✔ |
| Unknown `sub` → empty list, not 404 | ✔ | ✔ |
| Mail send valid → 202 + id; repeat with same key → same id, one send | ✔ | ✔ (to test address) |
| Mail send 6 recipients / bad domain / HTML body → 422 | ✔ | ✔ |
| Upstream 500 → 503 `backend-unavailable`; breaker opens after 5 | ✔ (fault injection) | ✔ |
| Upstream slow (6 s) → 504 | ✔ (fault injection) | — |

## 12. Tests (service level)

| # | Case |
|---|---|
| AD1 | No `Authorization` → 401 `unauthenticated` |
| AD2 | Assertion fixtures: expired, wrong `iss`, wrong `aud` (no `adapters`), `alg:none`, tampered → 401 `assertion-invalid` |
| AD3 | `scp` lacks `noten:read` → 403 `scope-not-granted`, audited |
| AD4 | Student calls mail → 403 `role-not-allowed` |
| AD5 | App A's assertion cannot read data of the `sub` in app B's assertion (there is no parameter to name another user; fuzz query/body/path for `sub`, `user`, `id`) |
| AD6 | Rate limit: 21st mail in an hour → 429 + `Retry-After`; counters are per `(azp, sub)` |
| AD7 | Idempotent replay returns identical body; a different user using the same key sends normally |
| AD8 | Breaker lifecycle: 5 failures → open → 503 fast; after 30 s one trial → closed on success |
| AD9 | Audit lines contain no body fields; `sub_hash` stable across requests, differs between users |
| AD10 | `readyz` stays 200 when a legacy backend is down; `/v1/status` shows breaker open |
| AD11 | OpenAPI response validation: server refuses to return a field not in the schema (test by a deliberately wrong mock) |
| AD12 | JWKS rotation: after the gateway adds `next`, adapters accept assertions signed by either key |

## 13. Open points

- Mail API path (EWS vs Graph vs SMTP + IMAP) and whether impersonation is available — Exchange admin, before 26.11.
- Who provisions `stage` datasets and in what form (AF-15, "Infrastrukturanbieter") — client.
- Audit retention and the lawful basis for logging `sub_hash` (Datenschutz) — before the pilot.
- E-Akte contract beyond the stub — nothing is known about the interface yet.
