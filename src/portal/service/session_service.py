"""SessionService: lesende Geschäftslogik für Sessions."""

from __future__ import annotations

from typing import Final

from loguru import logger

from ..auth.sessions import SessionStore
from .exceptions import NotFoundError
from .session_dto import SessionDTO


class SessionService:
    """Service-Klasse mit Geschäftslogik für Sessions."""

    def __init__(self, repo: SessionStore) -> None:
        """Konstruktor mit abhängigem SessionStore."""
        self.repo: SessionStore = repo

    def find_by_id(self, sid: str) -> SessionDTO:
        """Suche mit der Session-ID.

        :param sid: Session-ID aus dem Cookie
        :return: Die gefundene Session
        :rtype: SessionDTO
        :raises NotFoundError: Falls keine Session gefunden wurde
        """
        session: Final = self.repo.get(sid)
        if session is None:
            logger.debug("Session nicht gefunden")
            raise NotFoundError
        return SessionDTO(session)
