"""AuthRouter: Abmelden mit Bestätigungsseite und CSRF-geschütztem POST (04 §8, Test UI14)."""

from typing import Final

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from loguru import logger
from starlette.exceptions import HTTPException

from portal.web.deps import OptionalSession, PortalDep, SessionWriteServiceDep

router: Final = APIRouter(tags=["Authentifizierung"])


@router.get("/logout", response_class=HTMLResponse)
def logout_confirm(request: Request, portal: PortalDep, session: OptionalSession) -> Response:
    """Bestätigungsseite zum Abmelden.

    :param request: Injiziertes Request-Objekt von FastAPI bzw. Starlette
    :param portal: Injizierter Portal-Kontext
    :param session: Angemeldete Session oder None
    :return: Response mit der Bestätigungsseite, ohne Session Redirect auf die Startseite
    :rtype: Response
    """
    if session is None:
        return RedirectResponse("/", status_code=302)
    logger.debug("sub={}", session.sub)
    return portal.views.page(
        request, "pages/logout.html", title=portal.t("logout.title"), session=session, show_nav=False
    )


@router.post("/logout")
def logout(
    portal: PortalDep,
    service: SessionWriteServiceDep,
    session: OptionalSession,
    csrf: str = Form(""),
) -> Response:
    """Abmelden: Portal-Session beenden, Cookie löschen und bei OIDC die Session beim IdP beenden.

    :param portal: Injizierter Portal-Kontext
    :param service: Injizierter Service für Geschäftslogik
    :param session: Angemeldete Session oder None
    :param csrf: CSRF-Token aus dem Formular
    :return: Redirect zur Abmeldung beim IdP (OIDC) bzw. auf die Startseite
    :rtype: Response
    :raises HTTPException: 400, falls keine Session vorhanden ist
    :raises InvalidCsrfError: Falls das CSRF-Token nicht passt
    """
    if session is None:
        raise HTTPException(400)
    logger.debug("sub={}", session.sub)
    service.delete(session.sid, csrf)
    # Bei OIDC auch die Session beim IdP beenden, sonst meldet der nächste Login ohne Passwort wieder an.
    idp_url: Final = portal.login_service.end_session_url(session) if portal.login_service else None
    response: Final = RedirectResponse(idp_url or "/", status_code=303)
    response.delete_cookie(portal.cfg.session_cookie, path="/")
    return response
