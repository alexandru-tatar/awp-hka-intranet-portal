"""bwSync&Share: Fehlertypen (``AdapterError.type``).

Nur Konstanten. Bedeutung und typische Reaktion stehen in ``README.md`` (Abschnitt „Fehler“); allgemeine Typen
(``backend-unavailable`` usw.) in ``platform_sdk.adapters.transport``.
"""

from __future__ import annotations

NOT_LINKED = "bwsync-not-linked"  # 403: Konto ist nicht verbunden
LINK_INVALID = "bwsync-link-invalid"  # 403: Verbindung gilt nicht mehr (App-Passwort widerrufen)
FORBIDDEN = "bwsync-forbidden"  # 403: bwSync&Share verweigert genau diese Aktion
NOT_FOUND = "bwsync-not-found"  # 404
EXISTS = "bwsync-exists"  # 409/412: Ziel gibt es schon (nie überschrieben)
PARENT_MISSING = "bwsync-parent-missing"  # 409: Elternordner fehlt
CONFLICT = "bwsync-conflict"  # 409: sonstiger Konflikt in bwSync&Share
TOO_LARGE = "bwsync-too-large"  # 413: Upload größer als die Grenze des Adapters (10 MB)
LOCKED = "bwsync-locked"  # 423: in bwSync&Share gesperrt (z. B. dort geöffnet)

LINK_PROBLEMS = frozenset({NOT_LINKED, LINK_INVALID})  # die Person muss (neu) verbinden
