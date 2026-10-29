PORT ?= 8000

.PHONY: setup kit contrast dev dev-oidc idp-up idp-down server-up server-down test docs

COMPOSE = extras/compose

setup:
	uv sync

kit:
	uv run python kit/tools/build.py

contrast:
	uv run python kit/tools/contrast.py

dev: kit
	uv run uvicorn portal.dev:app --reload --reload-dir src --reload-dir dev --port $(PORT)

# Echte Anmeldung: Keycloak + Redis müssen laufen (make idp-up), PORT muss zur redirect_uri passen.
dev-oidc: kit
	PORTAL_CONFIG=dev/gateway.oidc.yml uv run uvicorn portal.dev:app --reload --reload-dir src --reload-dir dev --port $(PORT)

# Nur Redis + Keycloak, das Portal läuft auf dem Host (make dev-oidc).
idp-up:
	docker compose -f $(COMPOSE)/redis/compose.yml up -d
	docker compose -f $(COMPOSE)/keycloak/compose.yml up -d --build

idp-down:
	docker compose -f $(COMPOSE)/keycloak/compose.yml down
	docker compose -f $(COMPOSE)/redis/compose.yml down

# Alles im Container: Redis, Keycloak und Portal-Backend (http://localhost:8000).
server-up:
	docker compose -f $(COMPOSE)/server/compose.yml up -d --build

server-down:
	docker compose -f $(COMPOSE)/server/compose.yml down

test: contrast
	uv run pytest -q tests

# API-Dokumentation als HTML aus den Docstrings: docs/api/_build/html/index.html
# portal.dev bleibt draußen, weil der Import die Anwendung erzeugt.
docs:
	rm -rf docs/api/generated docs/api/_build
	uv run --group doc sphinx-apidoc --force --separate --module-first --implicit-namespaces \
		-o docs/api/generated src/portal src/portal/dev.py
	uv run --group doc python -m sphinx -b html -W --keep-going docs/api docs/api/_build/html
