"""bwSync&Share: Regeln für Namen und Pfade, wie der Adapter sie durchsetzt, und Daten für Anzeigen.

Pfade sind relativ zur Wurzel des Kontos (``"Studium/plan.pdf"``); ``""`` ist die Wurzel. Kein HTML, keine Texte.
"""

from __future__ import annotations

from pathlib import PurePosixPath

MAX_NAME = 255  # Zeichen je Name
MAX_PATH = 1024  # Zeichen je Pfad
FORBIDDEN_CHARS = "/\\:%?#"  # in Namen nicht erlaubt (kann der Adapter nicht verarbeiten)


def valid_name(name: str) -> bool:
    """Ein Name (Datei oder Ordner): 1–255 Zeichen, ohne ``FORBIDDEN_CHARS``, Steuerzeichen und Leerraum außen."""
    return (
        0 < len(name) <= MAX_NAME
        and name not in (".", "..")
        and name == name.strip()
        and not any(c in FORBIDDEN_CHARS for c in name)
        and name.isprintable()
    )


def clean_name(raw: str | None) -> str:
    """Nur der letzte Teil eines Namens (z. B. aus einem Upload), ohne Pfad und Steuerzeichen; danach ``valid_name``."""
    name = PurePosixPath((raw or "").replace("\\", "/")).name
    return "".join(c for c in name if c.isprintable()).strip()


def valid_path(path: str, *, root: bool = True) -> bool:
    """Relativer Pfad aus gültigen Namen; ``""`` (Wurzel) nur mit ``root=True``."""
    if path == "":
        return root
    return len(path) <= MAX_PATH and all(valid_name(part) for part in path.split("/"))


def join(folder: str, name: str) -> str:
    return f"{folder}/{name}" if folder else name


def parent_of(path: str) -> str:
    return path.rsplit("/", 1)[0] if "/" in path else ""


def name_of(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def breadcrumbs(path: str) -> list[dict[str, str]]:
    """Teile des Pfads für eine Pfadleiste, ohne Wurzel: ``"a/b"`` → ``[{name: a, path: a}, {name: b, path: a/b}]``."""
    items: list[dict[str, str]] = []
    so_far = ""
    for part in path.split("/") if path else []:
        so_far = join(so_far, part)
        items.append({"name": part, "path": so_far})
    return items
