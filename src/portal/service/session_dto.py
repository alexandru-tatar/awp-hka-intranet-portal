"""DTO-Klasse für Sessions (Service-Schicht)."""

from __future__ import annotations

from dataclasses import dataclass

from ..auth.sessions import Session


@dataclass(eq=False, slots=True, kw_only=True)
class SessionDTO:
    """DTO-Klasse für Session-Daten (Service-Schicht)."""

    sid: str
    sub: str
    name: str
    roles: frozenset[str]
    csrf: str
    id_token: str | None

    def __init__(self, session: Session) -> None:
        """Initialisierung von SessionDTO durch ein Session-Objekt des Stores.

        :param session: Session-Objekt aus dem Session-Store
        """
        self.sid = session.sid
        self.sub = session.sub
        self.name = session.name
        self.roles = session.roles
        self.csrf = session.csrf
        self.id_token = session.id_token
