# Fixture: gleiche fünf Befehle wie im JavaScript-Starter, nur RUNNER unterscheidet sich.
RUNNER := python -m
.PHONY: dev start test lint docker
dev:    ; $(RUNNER) uvicorn src.app.main:app --reload --host 0.0.0.0 --port 8080
start:  ; $(RUNNER) src.server
test:   ; $(RUNNER) pytest -q
lint:   ; $(RUNNER) ruff check .
docker: ; docker build -t starter-python-example:local .
