"""Dokumentation unter ``/_portal/docs``: Speicher (Seiten, Versionen, Dateien), HTML-Bereinigung und Seitenhülle.

``shell.html`` ist die Hülle der Seite (Stil, Kopf, Navigation, Skript), ``seed.html`` der Ausgangsstand der
Seiten, ``editor.js`` und ``editor.css`` der Editor und der Versionsverlauf.
"""

from .sanitize import sanitize_html
from .store import (
    DocChange,
    DocConflictError,
    DocEditor,
    DocNotFoundError,
    DocPage,
    DocPerson,
    DocReadOnlyError,
    DocStore,
    DocStoreError,
    DocVersion,
)

__all__ = [
    "DocChange", "DocConflictError", "DocEditor", "DocPerson", "DocNotFoundError", "DocPage", "DocReadOnlyError", "DocStore",
    "DocStoreError", "DocVersion", "sanitize_html",
]
