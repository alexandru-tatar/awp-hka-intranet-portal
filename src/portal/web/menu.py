"""Hilfen für die View-Schicht (der Menübaum selbst kommt aus dem AppService, 04 §4)."""

from __future__ import annotations


def current_slug(current: str | None) -> str | None:
    """Slug der aktuellen Seite bestimmen.

    :param current: Pfad der Seite, z. B. ``/apps/noten/x?y``
    :return: ``noten``; bei allem anderen ``None``
    :rtype: str | None
    """
    if not current or not current.startswith("/apps/"):
        return None
    slug = current[len("/apps/"):].split("/", 1)[0].split("?", 1)[0]
    return slug or None
