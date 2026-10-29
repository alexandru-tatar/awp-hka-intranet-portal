"""FastAPI-Dependencies: der Portal-Kontext, die Services und die Frage, wer anfragt."""

from __future__ import annotations

from typing import Annotated, Callable

from fastapi import Depends, Request
from starlette.exceptions import HTTPException

from ..context import Portal
from ..service import (
    AppService,
    LoginRequiredError,
    LoginService,
    NotFoundError,
    SessionDTO,
    SessionService,
    SessionWriteService,
)


def get_portal(request: Request) -> Portal:
    """Portal-Kontext der Anwendung.

    :param request: Anfrage
    :return: Der Kontext aus ``app.state.portal``
    :rtype: Portal
    """
    return request.app.state.portal


PortalDep = Annotated[Portal, Depends(get_portal)]


def get_app_service(portal: PortalDep) -> AppService:
    """App-Service.

    :param portal: Portal-Kontext
    :return: Der Service
    :rtype: AppService
    """
    return portal.app_service


def get_session_service(portal: PortalDep) -> SessionService:
    """Lesender Session-Service.

    :param portal: Portal-Kontext
    :return: Der Service
    :rtype: SessionService
    """
    return portal.session_service


def get_session_write_service(portal: PortalDep) -> SessionWriteService:
    """Schreibender Session-Service.

    :param portal: Portal-Kontext
    :return: Der Service
    :rtype: SessionWriteService
    """
    return portal.session_write_service


def get_login_service(portal: PortalDep) -> LoginService:
    """Login-Service für OIDC.

    :param portal: Portal-Kontext
    :return: Der Service
    :rtype: LoginService
    :raises HTTPException: 404, falls ``auth_mode`` nicht ``oidc`` ist
    """
    if portal.login_service is None:
        raise HTTPException(404)
    return portal.login_service


def optional_session(request: Request, portal: PortalDep) -> SessionDTO | None:
    """Session der Anfrage, falls vorhanden.

    :param request: Anfrage; das Cookie heißt wie ``cfg.session_cookie``
    :param portal: Portal-Kontext
    :return: Die Session oder ``None`` ohne Cookie oder bei unbekannter Session
    :rtype: SessionDTO | None
    :raises redis.exceptions.RedisError: Falls Redis nicht antwortet
    """
    sid = request.cookies.get(portal.cfg.session_cookie)
    if sid is None:
        return None
    try:
        return portal.session_service.find_by_id(sid)
    except NotFoundError:
        return None


def require_session(session: Annotated[SessionDTO | None, Depends(optional_session)]) -> SessionDTO:
    """Session der Anfrage, die vorhanden sein muss.

    :param session: Session oder ``None``
    :return: Die Session
    :rtype: SessionDTO
    :raises LoginRequiredError: Falls keine Session vorhanden ist
    """
    if session is None:
        raise LoginRequiredError
    return session


def require_role(role: str) -> Callable[..., SessionDTO]:
    """Dependency-Fabrik: verlangt eine Rolle.

    :param role: Erforderliche Rolle
    :return: Dependency, die die Session liefert oder mit 403 abbricht
    :rtype: Callable[..., SessionDTO]
    """
    def dependency(session: Annotated[SessionDTO, Depends(require_session)]) -> SessionDTO:
        if role not in session.roles:
            raise HTTPException(403)
        return session
    return dependency


LoginServiceDep = Annotated[LoginService, Depends(get_login_service)]
AppServiceDep = Annotated[AppService, Depends(get_app_service)]
SessionWriteServiceDep = Annotated[SessionWriteService, Depends(get_session_write_service)]
OptionalSession = Annotated[SessionDTO | None, Depends(optional_session)]
CurrentSession = Annotated[SessionDTO, Depends(require_session)]
AdminSession = Annotated[SessionDTO, Depends(require_role("platform-admin"))]
