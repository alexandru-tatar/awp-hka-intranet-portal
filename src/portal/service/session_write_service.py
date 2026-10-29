"""SessionWriteService: schreibende Geschäftslogik für Sessions."""

from __future__ import annotations

from typing import Final, Mapping

from loguru import logger

from ..auth.dev_users import DevUser
from ..auth.sessions import SessionStore
from .exceptions import InvalidCsrfError, UnknownUserError
from .session_dto import SessionDTO


class SessionWriteService:
    """Service-Klasse mit Geschäftslogik zum Anlegen und Beenden von Sessions."""

    def __init__(self, repo: SessionStore, dev_users: Mapping[str, DevUser]) -> None:
        """Konstruktor mit abhängigem SessionStore und den Testbenutzern."""
        self.repo: SessionStore = repo
        self.dev_users: Mapping[str, DevUser] = dev_users

    def create(self, user_id: str) -> SessionDTO:
        """Eine Session für einen Testbenutzer anlegen (Ersatz für OIDC).

        :param user_id: ID des Testbenutzers aus dev/users.yml
        :return: Die neue Session
        :rtype: SessionDTO
        :raises UnknownUserError: Falls der Benutzer nicht existiert
        """
        dev_user: Final = self.dev_users.get(user_id)
        if dev_user is None:
            raise UnknownUserError(user_id)

        session: Final = self.repo.create(
            sub=f"dev:{dev_user.id}", name=dev_user.name, roles=frozenset(dev_user.roles)
        )
        logger.debug("sub={}", session.sub)
        return SessionDTO(session)

    def create_for_subject(
        self, sub: str, name: str, roles: frozenset[str], id_token: str | None = None
    ) -> SessionDTO:
        """Eine Session nach erfolgreicher IdP-Anmeldung anlegen.

        :param sub: Subject des IdP
        :param name: Anzeigename
        :param roles: Rollen aus dem Role-Mapping
        :param id_token: ID-Token des IdP, für die spätere Abmeldung beim IdP
        :return: Die neue Session
        :rtype: SessionDTO
        """
        session: Final = self.repo.create(sub=sub, name=name, roles=roles, id_token=id_token)
        logger.debug("sub={}", session.sub)
        return SessionDTO(session)

    def discard(self, sid: str) -> None:
        """Eine Session ohne CSRF-Prüfung beenden (Rotation beim Login).

        :param sid: Session-ID
        """
        self.repo.delete(sid)

    def delete(self, sid: str, csrf: str) -> None:
        """Eine Session beenden, sofern das CSRF-Token passt.

        :param sid: Session-ID
        :param csrf: CSRF-Token aus dem Formular
        :raises InvalidCsrfError: Falls die Session fehlt oder das Token nicht passt
        """
        session: Final = self.repo.get(sid)
        if session is None or not session.csrf_matches(csrf):
            raise InvalidCsrfError
        self.repo.delete(sid)
