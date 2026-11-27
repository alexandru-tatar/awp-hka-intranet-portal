"""FastAPI-Dependencies: der Portal-Kontext, die Services und die Frage, wer anfragt."""

from __future__ import annotations

import secrets
from typing import Annotated, Callable

from fastapi import Depends, Request
from starlette.exceptions import HTTPException

from ..context import Portal
from ..service import (
    AdminService,
    AppService,
    DocService,
    DocWriteService,
    InvalidCsrfError,
    LoginRequiredError,
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


def get_admin_service(portal: PortalDep) -> AdminService:
    """Service der Verwaltungsseite.

    :param portal: Portal-Kontext
    :return: Der Service
    :rtype: AdminService
    """
    return portal.admin_service


def get_doc_service(portal: PortalDep) -> DocService:
    """Lesender Service der Dokumentation.

    :param portal: Portal-Kontext
    :return: Der Service
    :rtype: DocService
    """
    return portal.doc_service


def get_doc_write_service(portal: PortalDep) -> DocWriteService:
    """Schreibender Service der Dokumentation.

    :param portal: Portal-Kontext
    :return: Der Service
    :rtype: DocWriteService
    """
    return portal.doc_write_service


def can_read_docs(cfg_docs, session: SessionDTO | None) -> bool:
    """Ob eine Session die Dokumentation lesen darf.

    :param cfg_docs: Abschnitt ``docs`` der Konfiguration (:class:`~portal.core.config.DocsConfig`)
    :param session: Session oder ``None``
    :return: ``True`` bei ``read_roles: all`` für jede Session, sonst mit einer Lese- oder Bearbeitungsrolle
    :rtype: bool
    """
    if session is None:
        return False
    if "*" in cfg_docs.read_roles:
        return True
    return bool(session.roles & (set(cfg_docs.read_roles) | set(cfg_docs.edit_roles)))


def can_edit_docs(portal: Portal, session: SessionDTO | None) -> bool:
    """Ob eine Session die Dokumentation bearbeiten darf: Bearbeitungsrolle oder Freigabe auf der Verwaltungsseite.

    :param portal: Portal-Kontext
    :param session: Session oder ``None``
    :return: ``True``, falls die Person bearbeiten darf
    :rtype: bool
    """
    if session is None:
        return False
    return bool(session.roles & set(portal.cfg.docs.edit_roles)) or portal.doc_service.is_editor(session.sub)


def require_docs_reader(portal: PortalDep, session: Annotated[SessionDTO, Depends(require_session)]) -> SessionDTO:
    """Session, die die Dokumentation lesen darf.

    :param portal: Portal-Kontext
    :param session: Angemeldete Session
    :return: Die Session
    :rtype: SessionDTO
    :raises HTTPException: 403 ohne passende Rolle
    """
    if not can_read_docs(portal.cfg.docs, session):
        raise HTTPException(403)
    return session


def require_docs_editor(portal: PortalDep, session: Annotated[SessionDTO, Depends(require_session)]) -> SessionDTO:
    """Session, die die Dokumentation bearbeiten darf.

    :param portal: Portal-Kontext
    :param session: Angemeldete Session
    :return: Die Session
    :rtype: SessionDTO
    :raises HTTPException: 403 ohne passende Rolle
    """
    if not can_edit_docs(portal, session):
        raise HTTPException(403)
    return session


def check_csrf(session: SessionDTO, token: str) -> None:
    """CSRF-Token eines Formulars prüfen (zeitkonstanter Vergleich).

    :param session: Angemeldete Session
    :param token: Token aus dem Formular
    :raises InvalidCsrfError: Falls das Token nicht passt
    """
    if not secrets.compare_digest(token.encode(), session.csrf.encode()):
        raise InvalidCsrfError


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


def optional_session(request: Request, portal: PortalDep) -> SessionDTO | None:
    """Session der Anfrage, falls vorhanden.

    :param request: Anfrage; das Cookie heißt wie ``cfg.session_cookie``
    :param portal: Portal-Kontext
    :return: Die Session oder ``None`` ohne Cookie oder bei unbekannter Session
    :rtype: SessionDTO | None
    """
    if portal.cfg.auth_mode == "gateway":
        return getattr(request.state, "gateway_user", None)
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


AdminServiceDep = Annotated[AdminService, Depends(get_admin_service)]
AppServiceDep = Annotated[AppService, Depends(get_app_service)]
DocServiceDep = Annotated[DocService, Depends(get_doc_service)]
DocWriteServiceDep = Annotated[DocWriteService, Depends(get_doc_write_service)]
SessionWriteServiceDep = Annotated[SessionWriteService, Depends(get_session_write_service)]
OptionalSession = Annotated[SessionDTO | None, Depends(optional_session)]
CurrentSession = Annotated[SessionDTO, Depends(require_session)]
AdminSession = Annotated[SessionDTO, Depends(require_role("platform-admin"))]
DocsReader = Annotated[SessionDTO, Depends(require_docs_reader)]
DocsEditor = Annotated[SessionDTO, Depends(require_docs_editor)]
