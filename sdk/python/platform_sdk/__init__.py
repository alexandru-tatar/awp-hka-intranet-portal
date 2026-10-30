"""Portal-SDK für Python (vorläufig, nach Architekturvorschlag 06-portal-sdk.md).

Verwaltete Dateien: nicht verändern (sonst PF-103). Ersatz durch `make sdk-update`,
sobald die Plattform das SDK liefert.
"""

from __future__ import annotations

from .context import User
from .errors import AdapterError
from .portal import Portal

__all__ = ["AdapterError", "Portal", "User"]
