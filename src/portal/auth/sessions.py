"""Sessions und Session-Stores.

``MemorySessionStore`` ist der Store für den Dev-Modus ohne Redis; ``RedisSessionStore`` (in
:mod:`portal.auth.redis_sessions`) erfüllt denselben Vertrag. Beide liefern die Form
``sub, name, roles, csrf`` (02 §4), damit Menü-Filter und Logout mit CSRF-Schutz gleich arbeiten.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Session:
    """Eine angemeldete Session.

    :ivar sid: Session-ID (Wert des Cookies)
    :ivar sub: Subject des IdP
    :ivar name: Anzeigename
    :ivar roles: Rollen
    :ivar csrf: CSRF-Token für Formulare
    :ivar id_token: ID-Token des IdP, nur als ``id_token_hint`` für die Abmeldung beim IdP
    """
    sid: str
    sub: str
    name: str
    roles: frozenset[str]
    csrf: str
    id_token: str | None = None

    def has_role(self, role: str) -> bool:
        """Ob die Session eine Rolle hat.

        :param role: Gesuchte Rolle
        :return: ``True``, falls vorhanden
        :rtype: bool
        """
        return role in self.roles

    def csrf_matches(self, token: str) -> bool:
        """Ob das Token zum CSRF-Token der Session passt (zeitkonstanter Vergleich).

        :param token: Token aus dem Formular
        :return: ``True`` bei Übereinstimmung
        :rtype: bool
        """
        return secrets.compare_digest(token, self.csrf)


class SessionStore(Protocol):
    """Vertrag eines Session-Stores: Speicher im Dev-Modus, Redis bei OIDC."""

    def create(self, sub: str, name: str, roles: frozenset[str], id_token: str | None = None) -> Session:
        """Eine Session anlegen.

        :param sub: Subject des IdP
        :param name: Anzeigename
        :param roles: Rollen
        :param id_token: ID-Token des IdP für die Abmeldung beim IdP
        :return: Die neue Session
        :rtype: Session
        """
        ...

    def get(self, sid: str | None) -> Session | None:
        """Eine Session suchen.

        :param sid: Session-ID, ``None`` oder leer ergibt ``None``
        :return: Die Session oder ``None``
        :rtype: Session | None
        """
        ...

    def delete(self, sid: str) -> None:
        """Eine Session löschen; eine unbekannte ID wird ignoriert.

        :param sid: Session-ID
        """
        ...

    def ping(self) -> bool:
        """Ob der Store erreichbar ist.

        :return: ``True``, falls erreichbar
        :rtype: bool
        """
        ...


class MemorySessionStore:
    """Session-Store im Prozessspeicher; alle Sessions gehen beim Neustart verloren."""
    def __init__(self) -> None:
        """Konstruktor mit leerem Speicher."""
        self._sessions: dict[str, Session] = {}

    def create(self, sub: str, name: str, roles: frozenset[str], id_token: str | None = None) -> Session:
        """Eine Session mit zufälliger ID und zufälligem CSRF-Token anlegen.

        :param sub: Subject des IdP
        :param name: Anzeigename
        :param roles: Rollen
        :param id_token: ID-Token des IdP für die Abmeldung beim IdP
        :return: Die neue Session
        :rtype: Session
        """
        session = Session(
            sid=secrets.token_urlsafe(32),
            sub=sub,
            name=name,
            roles=roles,
            csrf=secrets.token_urlsafe(16),
            id_token=id_token,
        )
        self._sessions[session.sid] = session
        return session

    def get(self, sid: str | None) -> Session | None:
        """Eine Session suchen.

        :param sid: Session-ID
        :return: Die Session oder ``None``
        :rtype: Session | None
        """
        return self._sessions.get(sid) if sid else None

    def delete(self, sid: str) -> None:
        """Eine Session löschen; eine unbekannte ID wird ignoriert.

        :param sid: Session-ID
        """
        self._sessions.pop(sid, None)

    def ping(self) -> bool:
        """Der Speicher ist immer erreichbar.

        :return: ``True``
        :rtype: bool
        """
        return True
