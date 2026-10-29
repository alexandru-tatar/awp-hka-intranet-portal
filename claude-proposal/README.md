# Component Specifications — Index

Implementation-level specifications for each component of the proposed architecture. **A proposal, not a decision.** The overview is `../08-software-architecture-proposal.md`, the first component-level pass is `../09-component-design.md`; these files go one level deeper: complete configuration, schemas, algorithms, error catalogs, tests and runbooks. Where a statement here conflicts with `08`/`09`, **this folder wins** (the conflicts are listed in §3 and in the dated notes at the end of `08` and `09`).

## 1. Reading order

| File | Component | Read it if you build / operate… |
|---|---|---|
| `01-edge.md` | Traefik: TLS, routing, forward-auth hook, header forcing | the edge, or you need to know why an app never sees a cookie |
| `02-gateway.md` | OIDC login, sessions, `/auth/verify`, assertion minting, key rotation | Package A |
| `03-registry.md` | SQLite registry, manifest contract, state machine, Traefik payload | Package A, pipeline |
| `04-portal-ui-and-design-kit.md` | portal pages, tokens, patterns, German copy, accessibility gate | Package B |
| `05-adapter-service.md` | Noten/Mail/E-Akte adapters, OpenAPI, abuse controls, audit | Package B |
| `06-portal-sdk.md` | Python and JavaScript SDK, shared fixtures, dev shim | Packages B and C |
| `07-starters-and-runtime.md` | the two golden masters, Makefile, Dockerfiles, reference apps, compose template | Package C |
| `08-ai-layer.md` | `AGENTS.md`, seven skills, rule→check map, Prüfskript | Package C |
| `09-pipeline-and-deploy.md` | central pipeline, conformance probe, `deploy.sh`, failure codes | Package D |
| `10-platform-ops.md` | platform Compose, VM layout, firewall, backup, upgrade, handover checklist | Package D, HKA-IT |

## 2. Shared naming table (single source — every file must agree with it)

| Thing | Value |
|---|---|
| Environments | `prod`, `stage`; Compose projects `portal-prod`, `portal-stage` |
| Hosts | `portal.hka.example`, `portal-stage.hka.example` (placeholders) |
| Published ports | prod 80/443; stage 8080/8443 |
| Platform services | `traefik`, `gateway` (+ registry + portal UI), `redis`, `adapters`, `keycloak` (stage only) |
| Networks (Compose names `<project>_<net>`) | `edge`, `ingress`, `core`, `apps`, `egress`, `idp` (stage only) |
| Subnets prod | ingress `172.29.10.0/29`, apps `172.29.11.0/24` (dynamic from `.128`), core `172.29.12.0/29`, egress `172.29.13.0/29` |
| Subnets stage | ingress `172.29.20.0/29`, apps `172.29.21.0/24`, core `172.29.22.0/29`, idp `172.29.23.0/29`, egress `172.29.24.0/29` |
| Fixed addresses (prod) | gateway: ingress `.2`, core `.3`, apps `.2`, egress `.2`; traefik: ingress `.3`, apps `.4`; redis: core `.2`; adapters: apps `.3`, egress `.3` |
| Gateway listeners | main `172.29.10.2:8000` (ingress only); apps-facing `172.29.11.2:8001` (apps only) |
| Adapter listener | `172.29.11.3:8002` |
| App listener | `:8080` inside the container |
| DNS aliases on `apps` | `portal-api` (gateway), `portal-adapters`, `app-<slug>` |
| App environment | `PORTAL_ENV`, `PORTAL_SLUG`, `PORTAL_BASE_PATH`, `PORTAL_API_URL=http://portal-api:8001`, `PORTAL_ADAPTERS_URL=http://portal-adapters:8002`, `PORTAL_ISSUER`, `PORT`, `DATA_DIR` |
| Cookies | `__Host-portal_sid` (session), `__Host-portal_login` (login binding) |
| Headers | `X-Portal-Assertion`, `X-Request-Id`, `X-Portal-Kit` |
| Redis key prefixes | `sess:`, `oidc:`, `rl:`, `usr:` |
| Users | `deployer`, `ci`; groups `portal-admins`, `portal-secrets` (gid 10100) |
| Container uids | gateway 10001, adapters 10002, apps 10001, redis 999 |
| VM paths | `/opt/portal`, `/etc/portal/{secrets,apps}/<env>`, `/var/lib/portal/<env>`, `/var/backups/portal/<env>`, `/var/log/portal` |
| Image registry | `127.0.0.1:5000`, repositories `apps/<slug>`, deploy by digest |
| Python / Node | Python 3.12, Node 24 LTS (⚑ pin) |
| Assertion | RS256, `v: 1`, TTL 60 s, `aud` ∋ slug, `portal`, optionally `adapters` |
| Failure codes | `PF-101…113` (author-side checks), `PF-201…205` (deploy) |
| Rule IDs | `R-DES-n`, `R-A11Y-n`, `R-UI-n`, `R-SCHN-n`, `R-PORT-n`, `R-PF-n`, `R-SEC-n` |

## 3. Revisions to `08` and `09` found while writing these files

R1–R10 are in `../09-component-design.md`. R11–R27 are new:

| # | Defect found | Resolution | Where |
|---|---|---|---|
| R11 | `/_portal/nav` placed on :8000 although apps may reach only :8001 | apps-facing listener :8001 serves JWKS and `/nav` | `02` §1, §3 |
| R12 | `PathPrefix(/apps/x)` also matches `/apps/xfoo/…` | `Path ∥ PathPrefix(/…/)` + redirect; segment-exact slug parsing | `01` §5, `02` §6 |
| R13 | OIDC `state` not bound to the browser (login CSRF) | `__Host-portal_login` cookie must match the Redis entry; `next` sanitised | `02` §4 |
| R14 | in-memory snapshot breaks with several workers | exactly one worker; atomic snapshot swap | `02` §1 |
| R15 | `make test` cannot judge contrast without a browser | two-tier accessibility gate | `04` §9, `07` §2.1 |
| R16 | mail adapter could be a phishing relay | recipient allow-list, caps, plain text, footer | `05` §6.1 |
| R17 | compose template referenced an undefined health script | each image defines its own `HEALTHCHECK`; template does not override | `07` §2.3, §10 |
| R18 | authors cannot set CI variables, so who sets secrets? | explicit request process | `09-pipeline` §7 |
| R19 | audit contained `sub` in clear | HMAC-pseudonymised `sub_hash` | `02` §10, `05` §9 |
| R20 | per-app `adapters` network redundant; network membership unspecified | final network plan | `10` §4.1 |
| R21 | real client IP unknown | `trustedIPs` config + open question to HKA-IT | `01` §7 |
| R22 | file-provider directory is hard to split static vs generated, needs shared writable volume | Traefik **HTTP provider** polling `/internal/traefik-config` (fallback: file provider) | `01` §3, §5 |
| R23 | a container with an IP on `apps` reaches every listening port | listeners bound to fixed container IPs; peer check on :8000 | `02` §1 |
| R24 | registry token and API reachable by the `ci` user via host port | no host port; registry operated through `docker compose exec gateway gateway-cli`; manifest stage is offline | `03` §4, `09-pipeline` §3 |
| R25 | an app slug could collide with a platform DNS name | alias `app-<slug>` | `07` §10 |
| R26 | pipeline gates called author-editable entry points (`make`, poe, npm scripts) | central tools with central config; managed files verified by hash | `09-pipeline` §1, §3 |
| R27 | no way to enumerate an app's routes for the fail-closed probe | `PORTAL_PROBE=1` route table printed by the SDK; absence fails | `09-pipeline` §4, `06` |

## 4. Consolidated ⚑ list (confirm before relying on it)

| Area | Item | File |
|---|---|---|
| Traefik | HTTP provider stable + keeps last good config on failed poll | `01` |
| Traefik | empty-valued header entries delete headers (request and response) | `01` |
| Traefik | `authResponseHeaders` replaces client-supplied same-named headers | `01` |
| Traefik | `Path`/`PathPrefix` string-prefix semantics | `01` |
| Traefik | forwardAuth fails closed when the gateway is unreachable | `01` |
| Compose | `uid/gid/mode` on file secrets outside Swarm (design uses `group_add` instead) | `10` |
| Compose | `up --wait` honours image `HEALTHCHECK` | `07`, `09-pipeline` |
| Podman | `--format docker` keeps `HEALTHCHECK`; rootless build on the VM's OS | `09-pipeline` |
| Git platform | non-overridable CI mechanism and tier (GitLab external CI path / protected branches; GitHub rulesets) | `09-pipeline` |
| Registry | garbage collection needs `REGISTRY_STORAGE_DELETE_ENABLED` | `09-pipeline` |
| Keycloak | start flags and relative path per pinned version | `10` |
| SDK | FastAPI ≥ 0.115, Express 5, `node:sqlite` stability in Node 24 | `06`, `07` |
| AI tools | formats of generated stubs for Claude Code, Cursor, Copilot | `08` |
| Pins | image digests, tool tags (placeholders are intentionally obvious) | `07`, `10` |

## 5. Consolidated open decisions

Carried from `../09-component-design.md` §14 and extended:

| # | Decision | Owner |
|---|---|---|
| 1 | Ask HKA-IT for: VM size (16 GB / 6 vCPU suggested), Proxmox backup schedule, wildcard DNS + certificate, network ranges, egress addresses, front-proxy/real-IP, certificate owner | Team → HKA |
| 2 | Git platform (28.10) and the matching non-overridable pipeline mechanism | Team |
| 3 | Who presses the manual deploy button; who is in `portal-admins` | Team + HKA-IT |
| 4 | Jest (Angebot §9.1) vs `node:test` (deck, this spec) | Team |
| 5 | Legacy credentials: impersonation vs split-secret; mail API path | Client / Exchange admin |
| 6 | Audit retention and lawful basis for `sub_hash` | Team + Datenschutz |
| 7 | `{kontakt}` string, legal links, design manual | HKA |
| 8 | Fine-grained roles (AF-11) and the Tresor (AF-13): priced scope or explicit exclusion | Client |
| 9 | H5 Referer gate before or after the Durchstich | Team |
| 10 | Owner of the quality test after the project ends (`02-open-questions.md` §10) | Client |

## 6. Conventions

- **⚑** marks a dependence on third-party behaviour; none is presented as verified.
- Pseudocode is fenced as `text`; fenced `yaml`/`json`/`sql` blocks are machine-checked in CI of this documentation (parse; DDL executed in SQLite).
- German copy is final text, *Sie*-form, *einfache Sprache*; English prose is explanation.
- Tests are numbered per file (`E`, `G`, `REG`, `UI`, `AD`, `S`/`F`, `ST`, `AI`, `PL`, `OP`) so a defect report can cite one.
