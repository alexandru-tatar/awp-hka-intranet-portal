"""Sphinx-Konfiguration: API-Dokumentation nur aus den Docstrings in ``src/portal`` (autodoc)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

project = "HKA Portal"
language = "de"
extensions = ["sphinx.ext.autodoc"]

exclude_patterns = ["_build"]
html_theme = "alabaster"
html_title = "HKA Portal – API"

autodoc_member_order = "bysource"
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "private-members": True,
    "special-members": "__init__, __call__, __contains__",
    # Pakete exportieren Klassen per __all__ erneut; dokumentiert wird nur dort, wo sie definiert sind.
    "ignore-module-all": True,
}
