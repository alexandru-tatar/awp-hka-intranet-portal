"""Portal-SDK für Python (vorläufig, nach Architekturvorschlag 06-portal-sdk.md).

Verwaltete Dateien: nicht verändern (sonst PF-103). Ersatz durch `make sdk-update`,
sobald die Plattform das SDK liefert.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .context import User
    from .errors import AdapterError
    from .portal import Portal

__all__ = ["AdapterError", "Portal", "User"]

# Erst beim Zugriff laden (PEP 562): So läuft `python -m platform_sdk.verify_tree` auch dann, wenn eine Datei des SDK
# beschädigt ist, und meldet PF-103 statt eines Tracebacks.
_LAZY = {"User": ".context", "AdapterError": ".errors", "Portal": ".portal"}


def __getattr__(name: str) -> object:
    if name in _LAZY:
        return getattr(import_module(_LAZY[name], __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
