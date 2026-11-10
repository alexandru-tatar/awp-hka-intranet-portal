PORT ?= 8000

.PHONY: setup kit contrast dev idp-up idp-down test docs sdk-test sdk-release

COMPOSE = extras/compose

setup:
	uv sync

kit:
	uv run python kit/tools/build.py

contrast:
	uv run python kit/tools/contrast.py

dev: kit
	uv run uvicorn portal.dev:app --reload --reload-dir src --reload-dir dev --port $(PORT)

# Keycloak als IdP für das separate Security-Gateway (Repo security-gateway), nicht für das Portal selbst.
idp-up:
	docker compose -f $(COMPOSE)/keycloak/compose.yml up -d --build

idp-down:
	docker compose -f $(COMPOSE)/keycloak/compose.yml down

test: contrast sdk-test
	uv run pytest -q tests

# Portal-SDK (sdk/README.md): Tests und Freigabe nach sdk/dist/<sprache>/platform_sdk
sdk-test:
	PYTHONPATH=sdk/python uv run pytest -q sdk/python/tests
	cd sdk/javascript && { test -d node_modules || npm ci --no-audit --no-fund; } && npm test

sdk-release: sdk-test
	uv run python sdk/tools/release.py

# API-Dokumentation als HTML aus den Docstrings: docs/api/_build/html/index.html
# portal.dev bleibt draußen, weil der Import die Anwendung erzeugt.
docs:
	rm -rf docs/api/generated docs/api/_build
	uv run --group doc sphinx-apidoc --force --separate --module-first --implicit-namespaces \
		-o docs/api/generated src/portal src/portal/dev.py
	uv run --group doc python -m sphinx -b html -W --keep-going docs/api docs/api/_build/html
