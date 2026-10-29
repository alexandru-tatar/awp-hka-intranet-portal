# 07 — Starters and the Runtime Template

Implementation-level specification. Overview: `../09-component-design.md` §7. Two golden masters (Python/FastAPI and JavaScript/Express, Angebot §5.1/§5.4) produce apps that all look, start, test, build and run the same way. ⚑ = confirm at implementation; image digests are placeholders `sha256:REPLACE_AT_RELEASE` and **must be pinned when the starters are released**.

## 1. Managed vs. owned files

A starter is copied into an author's repository. Over time the platform must be able to update the parts it owns without touching the author's work.

| Class | Files | Rule |
|---|---|---|
| **Managed** (platform-owned, overwritten by `make template-update`) | `Makefile`, `AGENTS.md`, `.agents/**`, `.devcontainer/**`, `.editorconfig`, `.pre-commit-config.yaml`, `.stylelintrc.json`, `eslint.config.js` / ruff section marker, `tools/**`, `Dockerfile`, `platform_sdk/**` (via `sdk-update`) | Authors do not edit. Local additions go to `AGENTS.local.md` (imported by `AGENTS.md`). A diff is shown before overwriting. |
| **Owned** (author-owned, never touched) | `src/**`, `tests/**`, `manifest.json`, `README.md`, `data/` | Updates to the starter never write here. |
| **Generated** | `build/`, `requirements*.lock` (via `make lock`) | not committed (`build/`) / committed (`*.lock`) |

`make template-update` reads `template-files.json` from the platform repository at the pinned starter version (list of managed paths), shows `git diff`, and asks for confirmation. Starter releases are tags with release notes; there is no automatic update in the pilot.

## 2. Python starter (FastAPI)

```
python-starter/
├── AGENTS.md          .agents/skills/<7>/SKILL.md          (08-ai-layer.md)
├── .devcontainer/{devcontainer.json,Dockerfile}
├── .editorconfig  .gitignore  .pre-commit-config.yaml  .stylelintrc.json
├── Makefile  Dockerfile  pyproject.toml  requirements.lock  requirements-dev.lock
├── manifest.json  README.md
├── platform_sdk/                    # vendored, see 06
├── tools/{a11y-structural.mjs,package.json}   # shared with the Node starter
├── src/app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI app, portal.install, router wiring
│   ├── views.py                     # route handlers
│   ├── db.py                        # optional: sqlite3 helper on $DATA_DIR
│   ├── templates/page.html          # Jinja2, body fragment only (chrome comes from layout())
│   └── static/app.css               # tokens only, no hex colours
└── tests/{test_app.py,test_pages_a11y.py,conftest.py}
```

### 2.1 `pyproject.toml` (essentials)

```toml
[project]
name = "portal-app"
version = "0.1.0"
requires-python = ">=3.12,<3.13"
dependencies = ["fastapi>=0.115", "uvicorn>=0.30", "jinja2>=3.1", "PyJWT[crypto]>=2.9", "httpx>=0.27"]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=0.24", "ruff>=0.6", "poethepoet>=0.29"]

[tool.poe.tasks]
dev    = "uvicorn app.main:app --reload --host 0.0.0.0 --port 8080 --app-dir src"
start  = "uvicorn app.main:app --host 0.0.0.0 --port 8080 --app-dir src"
test   = ["_pytest", "_a11y"]
_pytest = "pytest -q"
_a11y  = "node tools/a11y-structural.mjs build/a11y"
lint   = ["_ruff", "_format", "_css", "_sdk"]
_ruff  = "ruff check src tests"
_format = "ruff format --check src tests"
_css   = "npx --prefix tools stylelint src/app/static/*.css"
_sdk   = "python -m platform_sdk.verify_tree"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "S", "TID"]

[tool.ruff.lint.flake8-tidy-imports.banned-api]
"requests".msg = "Andere Systeme nur über portal.adapters ansprechen (Regel R-SCHN-1)."
"httpx".msg    = "Andere Systeme nur über portal.adapters ansprechen (Regel R-SCHN-1)."
"urllib.request".msg = "Andere Systeme nur über portal.adapters ansprechen (Regel R-SCHN-1)."
"jwt".msg      = "Kein eigenes Login und keine eigene Token-Prüfung (Regel R-PORT-1)."
"passlib".msg  = "Kein eigenes Login (Regel R-PORT-1)."

[tool.ruff.lint.per-file-ignores]
"platform_sdk/**" = ["TID251", "S"]
```
`make test` renders every page through the ASGI test client into `build/a11y/*.html`; `a11y-structural.mjs` loads each file in jsdom and runs axe-core (structural rules only — contrast is gated in CI, R15).

### 2.2 `src/app/main.py` (the whole app skeleton)

```python
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from platform_sdk import Portal
from . import views

portal = Portal.from_env()                    # reads manifest.json and PORTAL_* variables
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)   # no auto-docs endpoints in production
portal.install(app)                           # verification middleware, /healthz, dev shim when enabled
app.mount(portal.url("/static"), StaticFiles(directory=Path(__file__).parent / "static"), name="static")
app.include_router(views.build_router(portal))
```

### 2.3 Dockerfile (Python)

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm@sha256:REPLACE_AT_RELEASE AS build
WORKDIR /w
COPY requirements.lock ./
RUN pip install --no-cache-dir --require-hashes --prefix=/install -r requirements.lock

FROM python:3.12-slim-bookworm@sha256:REPLACE_AT_RELEASE
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app \
 && mkdir /data && chown 10001:10001 /data
COPY --from=build /install /usr/local
WORKDIR /app
COPY --chown=10001:10001 platform_sdk ./platform_sdk
COPY --chown=10001:10001 src ./src
COPY --chown=10001:10001 manifest.json ./
USER 10001:10001
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=8080 PYTHONPATH=/app:/app/src DATA_DIR=/data
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-m", "platform_sdk.healthcheck"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--app-dir", "src"]
```
`platform_sdk.healthcheck` uses only the standard library (`urllib.request` to `http://127.0.0.1:8080/healthz`, timeout 2 s, exit 0/1) — no `curl` in the image (R17).

## 3. JavaScript starter (Express)

```
node-starter/
├── AGENTS.md   .agents/skills/<7>/SKILL.md
├── .devcontainer/  .editorconfig  .gitignore  .pre-commit-config.yaml  .stylelintrc.json
├── Makefile  Dockerfile  package.json  package-lock.json  eslint.config.js
├── manifest.json  README.md
├── platform_sdk/                     # vendored, see 06
├── tools/{a11y-structural.mjs,package.json}
├── src/
│   ├── app.js                        # Express app, portal.install
│   ├── routes.js
│   ├── views/page.njk                # Nunjucks body fragment
│   └── static/app.css
└── tests/{app.test.js,pages-a11y.test.js}
```

### 3.1 `package.json` (essentials)

```json
{
  "name": "portal-app",
  "version": "0.1.0",
  "type": "module",
  "engines": { "node": ">=24 <25" },
  "scripts": {
    "dev": "node --watch src/app.js",
    "start": "node src/app.js",
    "test": "node --test tests/ && node tools/a11y-structural.mjs build/a11y",
    "lint": "eslint . && npx --prefix tools stylelint \"src/static/*.css\" && node platform_sdk/verify_tree.js",
    "docker": "docker build -t app:local ."
  },
  "dependencies": { "express": "^5.0.0", "nunjucks": "^3.2.4", "jose": "^5.9.0" },
  "devDependencies": { "eslint": "^9.0.0" }
}
```
**Test runner decision (open, flagged):** Angebot §9.1 names *Jest* for JavaScript; the 22.10 deck shows `node:test` (`../06-praesentation-deck-review.md` C5). This spec uses the built-in `node --test` (zero dependencies, matches the deck). If the contract wording is kept, only the `test` script and two test files change. The team must align one of the two documents.

`eslint.config.js` restrictions (rule `R-SCHN-1`/`R-PORT-1`):
```js
export default [{
  files: ["src/**/*.js", "tests/**/*.js"],
  rules: {
    "no-restricted-imports": ["error", { paths: [
      { name: "axios", message: "Andere Systeme nur über portal.adapters ansprechen (R-SCHN-1)." },
      { name: "node-fetch", message: "dito" }, { name: "got", message: "dito" }, { name: "undici", message: "dito" },
      { name: "node:http", message: "dito" }, { name: "node:https", message: "dito" },
      { name: "jsonwebtoken", message: "Kein eigenes Login (R-PORT-1)." }, { name: "passport", message: "Kein eigenes Login (R-PORT-1)." }
    ]}],
    "no-restricted-globals": ["error", { name: "fetch", message: "Andere Systeme nur über portal.adapters ansprechen (R-SCHN-1)." }]
  }
}, { files: ["platform_sdk/**"], rules: { "no-restricted-imports": "off", "no-restricted-globals": "off" } }];
```
(`fetch` in *browser* scripts is not linted because app browser code is limited to files in `src/static/`, which the CSP restricts to same-origin; server-side `fetch` is what the rule targets.)

### 3.2 `src/app.js`

```js
import express from "express";
import nunjucks from "nunjucks";
import { Portal } from "../platform_sdk/index.js";
import { buildRoutes } from "./routes.js";

const portal = Portal.fromEnv();
const app = express();
app.disable("x-powered-by");
nunjucks.configure("src/views", { express: app, autoescape: true });
portal.install(app);                                        // verification, /healthz, dev shim
app.use(portal.url("/static"), express.static("src/static", { index: false }));
app.use(portal.basePath || "/", buildRoutes(portal));
app.listen(Number(process.env.PORT ?? 8080), "0.0.0.0");
```

### 3.3 Dockerfile (Node)

```dockerfile
# syntax=docker/dockerfile:1
FROM node:24-bookworm-slim@sha256:REPLACE_AT_RELEASE AS build
WORKDIR /w
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts

FROM node:24-bookworm-slim@sha256:REPLACE_AT_RELEASE
RUN mkdir /data && chown 10001:10001 /data
WORKDIR /app
COPY --from=build --chown=10001:10001 /w/node_modules ./node_modules
COPY --chown=10001:10001 platform_sdk ./platform_sdk
COPY --chown=10001:10001 src ./src
COPY --chown=10001:10001 package.json manifest.json ./
USER 10001:10001
ENV NODE_ENV=production PORT=8080 DATA_DIR=/data
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD ["node", "platform_sdk/healthcheck.js"]
CMD ["node", "src/app.js"]
```

## 4. The identical `Makefile`

```make
# MANAGED FILE — identical in both starters except RUNNER. Do not edit.
RUNNER := poe            # node-starter: RUNNER := npm run
.PHONY: dev start test lint docker sdk-update template-update ai-sync lock
dev:    ; $(RUNNER) dev
start:  ; $(RUNNER) start
test:   ; $(RUNNER) test
lint:   ; $(RUNNER) lint
docker: ; $(RUNNER) docker
sdk-update:      ; python3 tools/platform.py sdk-update $(VERSION)
template-update: ; python3 tools/platform.py template-update
ai-sync:         ; python3 tools/platform.py ai-sync
lock:            ; python3 tools/platform.py lock
```
The five documented commands are `dev`, `start`, `test`, `lint`, `docker`. The four maintenance targets are not part of the author's daily vocabulary and are listed in `README.md` under "Wartung". `tools/platform.py` is Python for both starters (the DevContainer of the Node starter also contains Python 3 for it; managed file, stdlib only).

`make docker` runs `docker build -t app:local .` — **the same Dockerfile the pipeline builds**, so "works in my container" means "works in the pipeline".

## 5. DevContainer

`.devcontainer/devcontainer.json` (Python starter; the Node starter differs in base image, extensions and `postCreateCommand`):
```json
{
  "name": "Portal-App (Python)",
  "build": { "dockerfile": "Dockerfile" },
  "features": { "ghcr.io/devcontainers/features/node:1": { "version": "24" } },
  "remoteUser": "vscode",
  "containerEnv": {
    "PORTAL_DEV": "1",
    "PORTAL_ENV": "development",
    "PORTAL_BASE_PATH": "",
    "PORT": "8080",
    "DATA_DIR": "/workspaces/app/data"
  },
  "forwardPorts": [8080],
  "portsAttributes": { "8080": { "label": "App", "onAutoForward": "openBrowser" } },
  "postCreateCommand": "pip install --require-hashes -r requirements.lock && pip install -r requirements-dev.lock && npm ci --prefix tools && pre-commit install",
  "customizations": {
    "vscode": {
      "extensions": ["ms-python.python", "charliermarsh.ruff", "editorconfig.editorconfig", "stylelint.vscode-stylelint"],
      "settings": {
        "editor.formatOnSave": true,
        "editor.rulers": [100],
        "python.defaultInterpreterPath": "/usr/local/bin/python",
        "files.eol": "\n"
      }
    }
  }
}
```
Design notes: no host mounts of secrets or `~/.ssh`; the author's AI assistant extension is **their own choice and licence** (`02-open-questions.md` §10: vendor-neutral); network is open in the DevContainer (it needs package registries) — the no-egress rule applies to production containers, not to development.

## 6. Pre-commit (secret safeguard 1 of 3)

```yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.0.0            # ⚑ pin the current release at starter release time
    hooks: [{ id: gitleaks }]
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.0.0            # ⚑ pin
    hooks: [{ id: ruff }, { id: ruff-format }]
  - repo: local
    hooks:
      - id: sdk-verify
        name: Portal-Bibliothek unverändert?
        entry: python -m platform_sdk.verify_tree
        language: system
        pass_filenames: false
```
(Node starter replaces the ruff hooks with an `eslint` local hook.) Placeholders `v8.0.0`/`v0.0.0` are deliberately obvious: **real tags must be pinned at release**.

## 7. Manifest examples

```json
{
  "slug": "noten",
  "name": "Noten-Übersicht",
  "category": "Studium",
  "menu": { "label": "Meine Noten", "icon": "table" },
  "roles": ["student"],
  "adapters": ["noten:read"],
  "version": "1.0.0"
}
```
```json
{
  "slug": "nachricht",
  "name": "Nachricht senden",
  "category": "Kommunikation",
  "menu": { "label": "Nachricht senden", "icon": "mail" },
  "roles": ["employee", "professor"],
  "adapters": ["mail:send"],
  "version": "1.0.0"
}
```

## 8. Reference app 1 — "Noten-Übersicht" (Python starter, Angebot §6)

| Requirement (Angebot) | Implementation |
|---|---|
| After login shows name and roles of the signed-in person | header block: "Angemeldet als {user.name} – Rollen: {roles}" (German role labels via a small map; unknown role shown as-is) |
| Table with module, semester, grade | `portal.adapters.noten.list_my_grades()` → data table pattern (`04` §7.4) with caption "Meine Noten" |
| Data from test data through the adapter | dev: SDK mock transport; stage: adapter `mock`/`stage`; prod: `live` once available |
| Read only | no form, no POST route |
| Logout ends the session | "Abmelden" link from `layout()` (`04` §8) |

Routes: `GET {base}/` only (plus `/healthz`). States: empty list → "Es liegen noch keine Noten vor."; `AdapterError` 403/503/504 → page with the error's German `detail` and the request id; 401 never reaches the handler.

Tests (`pytest`): renders table for fixture user; empty state; each `AdapterError` type shows the right message; page passes structural axe; request without assertion → 401; assertion with role `employee` → 403 via `requires("student")`; `layout()` contains skip link and `lang="de"`.

## 9. Reference app 2 — "Nachricht senden" (JavaScript starter, Angebot §6)

| Requirement (Angebot) | Implementation |
|---|---|
| After login shows name and roles | same header block |
| Form with subject and text | `GET {base}/` form using the field pattern (`04` §7.3); server-side validation (subject 1–120, text 1–5000) |
| Dialog with two buttons asks before sending | native `<dialog>` (`04` §7.2), buttons *Abbrechen* / *Senden*; **no-JS fallback:** `POST {base}/preview` renders a summary page with the same two buttons |
| Message goes through the adapter to a test address | `POST {base}/send` → `portal.adapters.mail.sendMessage({to:[TEST_RECIPIENT], …})`; `TEST_RECIPIENT` from `APP_MAIL_TEST_RECIPIENT` (default `test@test.hka.example`) |
| Logout ends the session | as above |

Success page: "Ihre Nachricht wurde zum Versand angenommen." Adapter problems (e.g. 429 `rate-limited`) are shown with their `detail`. The form is protected from double submission by the adapter's idempotency key (the app generates one key per rendered form and posts it back as a hidden field).

Tests (`node --test`): renders form; empty subject → error summary + field error; dialog markup contains exactly two buttons; send success with the mock transport; 429 shows "Zu viele Anfragen…"; no `fetch` in `src/` (lint); structural axe; request without assertion → 401.

## 10. The central compose template (applied by `deploy.sh`)

Authors never write this file. It lives in the platform repository (`deploy/app-compose.yml.j2`) and is rendered with `slug`, `digest`, `env_name`, `project` (`portal-prod`|`portal-stage`).

```yaml
name: "app-{{ env_name }}-{{ slug }}"
services:
  app:
    image: "127.0.0.1:5000/apps/{{ slug }}@{{ digest }}"
    restart: unless-stopped
    init: true
    stop_grace_period: 20s
    user: "10001:10001"
    read_only: true
    tmpfs: ["/tmp:size=64m,noexec,nosuid"]
    cap_drop: ["ALL"]
    security_opt: ["no-new-privileges:true"]
    pids_limit: 128
    mem_limit: 512m
    cpus: 0.5
    ulimits: { nofile: { soft: 1024, hard: 1024 } }
    env_file: ["/etc/portal/apps/{{ env_name }}/{{ slug }}.env"]
    environment:
      PORTAL_ENV: production
      PORTAL_SLUG: "{{ slug }}"
      PORTAL_BASE_PATH: "/apps/{{ slug }}"
      PORTAL_API_URL: "http://portal-api:8001"
      PORTAL_ADAPTERS_URL: "http://portal-adapters:8002"
      PORTAL_ISSUER: "https://{{ public_host }}/"
      PORT: "8080"
      DATA_DIR: /data
    volumes:
      - "data_{{ slug }}:/data"
    networks:
      apps:
        aliases: ["app-{{ slug }}"]
    logging:
      driver: json-file
      options: { max-size: "10m", max-file: "5" }
    # no healthcheck here on purpose: the image's own HEALTHCHECK is authoritative (R17);
    # the conformance probe (09-pipeline) fails images that do not define one.
networks:
  apps:
    external: true
    name: "{{ project }}_apps"
volumes:
  data_{{ slug }}:
    name: "{{ project }}_data_{{ slug }}"
```
Notes:
- **No `adapters` network** (R20): adapters are reachable on `apps`; authorization is the `scp` claim.
- **DNS alias `app-<slug>`** (R25): an app can never shadow `portal-api` or `portal-adapters` by choosing an unfortunate slug.
- The image's `HEALTHCHECK` feeds `docker compose up --wait` and `docker inspect`.
- Volume ownership: `/data` exists in the image owned by uid 10001; Docker copies content and ownership into a new named volume on first use.
- Limits are fixed in the pilot (0.5 vCPU / 512 MB, `02-open-questions.md` §6 default). A maintainer may add `deploy/limits/<slug>.yml` to raise them; authors cannot.
- Egress: the `apps` network is `internal: true` (`10-platform-ops.md`), so an app has no route to the internet or to HKA systems.

## 11. Persistence

Default: none (the reference apps keep no state). Python: stdlib `sqlite3` on `$DATA_DIR/app.db` via `db.py` (WAL, one connection per request). JavaScript: `node:sqlite` ⚑ (confirm stability in the pinned Node 24 minor) — otherwise a documented JSON-file store. Backup/restore of a volume: `platform.sh volume-backup <slug>` / `volume-restore` (`10-platform-ops.md`); automatic backup is explicitly out of scope (Angebot §5.2).

## 12. Tests for the starters themselves (run in the starter repository's CI)

| # | Case |
|---|---|
| ST1 | Both starters pass `make lint test docker` from a clean checkout in the DevContainer image |
| ST2 | `make dev` starts on :8080 with the dev shim; page reachable after dev login |
| ST3 | The two `Makefile`s differ only in the `RUNNER` line (diff test) |
| ST4 | The image runs as uid 10001 with `--read-only` and `--cap-drop=ALL` and passes its own HEALTHCHECK |
| ST5 | `docker inspect` shows a non-empty `Config.Healthcheck` |
| ST6 | Ruff/ESLint ban rules fire on a deliberate `import requests` / `fetch(…)` canary (`tests/canary/`, excluded from the normal run) |
| ST7 | Stylelint fails on a `color: #333` canary |
| ST8 | `sdk_verify` passes on a fresh starter, fails after editing one SDK byte |
| ST9 | Both reference apps pass the shared conformance probe (`09-pipeline-and-deploy.md` §4) |
| ST10 | `make template-update` never modifies `src/`, `tests/`, `manifest.json`, `README.md` |

## 13. Open points

- Test runner wording (§3.1): Jest in the Angebot vs `node:test` in the deck.
- Pinned image digests, gitleaks/ruff tags, Express/FastAPI versions: set at starter release.
- Whether `make lock` should be one of the documented commands (it is the only way to update dependencies); recommended: keep it a maintenance target.
