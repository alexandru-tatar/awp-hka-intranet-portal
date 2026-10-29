"""LoginService: OIDC-Anmeldung in zwei Schritten (02 §4)."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Final

from loguru import logger

from ..auth.oidc import OidcClient, OidcError
from ..auth.redirects import sanitize_next
from ..auth.redis_sessions import RedisLoginStore
from ..auth.roles import RoleMapper
from .exceptions import LoginFailedError
from .session_dto import SessionDTO
from .session_write_service import SessionWriteService


@dataclass(eq=False, slots=True, kw_only=True)
class StartedLogin:
    """Ergebnis von start: Ziel beim IdP und ID der Login-Transaktion (für das Cookie)."""

    url: str
    lid: str


@dataclass(eq=False, slots=True, kw_only=True)
class FinishedLogin:
    """Ergebnis von finish: neue Session und Zielpfad."""

    session: SessionDTO
    next: str


class LoginService:
    """Service-Klasse mit Geschäftslogik für die Anmeldung per OIDC."""

    def __init__(
        self,
        oidc: OidcClient,
        login_store: RedisLoginStore,
        role_mapper: RoleMapper,
        sessions: SessionWriteService,
    ) -> None:
        """Konstruktor mit OIDC-Client, Login-Store, Role-Mapper und Session-Service."""
        self.oidc: OidcClient = oidc
        self.login_store: RedisLoginStore = login_store
        self.role_mapper: RoleMapper = role_mapper
        self.sessions: SessionWriteService = sessions

    def start(self, next_path: str | None) -> StartedLogin:
        """Login-Transaktion anlegen und die Adresse beim IdP liefern.

        :param next_path: Gewünschter Zielpfad, wird gegen Open Redirects geprüft
        :return: Redirect-Ziel und Transaktions-ID
        :rtype: StartedLogin
        :raises LoginFailedError: Falls der IdP nicht erreichbar ist
        """
        lid: Final = secrets.token_urlsafe(16)
        state: Final = secrets.token_urlsafe(16)
        nonce: Final = secrets.token_urlsafe(16)
        verifier: Final = secrets.token_urlsafe(32)
        target: Final = sanitize_next(next_path)
        try:
            url: Final = self.oidc.authorization_url(state=state, nonce=nonce, verifier=verifier)
        except OidcError as exc:
            raise self._failed(f"discovery: {exc}") from exc
        self.login_store.put(lid, {"state": state, "nonce": nonce, "verifier": verifier, "next": target})
        logger.debug("next={}", target)
        return StartedLogin(url=url, lid=lid)

    def finish(
        self,
        lid: str | None,
        code: str | None,
        state: str | None,
        idp_error: str | None,
        old_sid: str | None,
    ) -> FinishedLogin:
        """Callback des IdP verarbeiten und eine neue Session anlegen.

        :param lid: Transaktions-ID aus dem Login-Cookie dieses Browsers
        :param code: Authorization Code
        :param state: State aus der Query
        :param idp_error: Fehlercode des IdP, falls vorhanden
        :param old_sid: Bisherige Session dieses Browsers, wird beendet (Rotation)
        :return: Neue Session und Zielpfad
        :rtype: FinishedLogin
        :raises LoginFailedError: Bei jedem Fehler; der Grund steht nur im Log
        """
        if not lid:
            raise self._failed("missing login cookie")
        record: Final = self.login_store.pop(lid)  # GETDEL: ein Callback pro Transaktion
        if record is None or not state or not secrets.compare_digest(record["state"], state):
            raise self._failed("unknown transaction or state mismatch")
        if idp_error:
            raise self._failed(f"idp error {idp_error}")
        if not code:
            raise self._failed("missing code")
        try:
            claims, id_token = self.oidc.claims_for_code(
                code=code, verifier=record["verifier"], nonce=record["nonce"]
            )
        except OidcError as exc:
            raise self._failed(str(exc)) from exc

        sub: Final = claims["sub"]
        roles: Final = self.role_mapper.map_roles(sub, claims)
        if old_sid:
            self.sessions.discard(old_sid)
        session: Final = self.sessions.create_for_subject(
            sub=sub,
            name=claims.get("name") or claims.get("preferred_username") or sub,
            roles=roles,
            id_token=id_token,
        )
        return FinishedLogin(session=session, next=record["next"])

    def end_session_url(self, session: SessionDTO) -> str | None:
        """Adresse beim IdP, die dessen Session beendet; sonst bliebe man dort angemeldet und der nächste Login ginge ohne Passwort durch.

        :param session: Die Session, die gerade beendet wird
        :return: Redirect-Ziel beim IdP oder ``None``, falls der IdP keine Abmeldung anbietet
        :rtype: str | None
        """
        return self.oidc.end_session_url(session.id_token)

    @staticmethod
    def _failed(reason: str) -> LoginFailedError:
        """Fehler protokollieren und als Exception liefern.

        :param reason: Grund, nur für das Log
        :return: Die Exception zum Auslösen
        :rtype: LoginFailedError
        """
        logger.warning("login_failure reason={}", reason)
        return LoginFailedError(reason)
