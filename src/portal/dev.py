"""ASGI-Einstiegspunkt: ``uvicorn portal.dev:app --reload``.

Die Konfiguration kommt aus der Umgebungsvariable ``PORTAL_CONFIG``, sonst aus
``dev/gateway.dev.yml``. Hier wird auch das Logging eingerichtet.
"""

import os
from pathlib import Path

from .app import create_app
from .core.config import load_config
from .core.log import configure_logging

_config = load_config(
    Path(os.environ.get("PORTAL_CONFIG", Path(__file__).resolve().parents[2] / "dev" / "gateway.dev.yml"))
)
configure_logging(_config.logging)
app = create_app(_config)
