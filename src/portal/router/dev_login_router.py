"""DevLoginRouter: Auswahl der Testpersonen statt OIDC.

Wird nur bei `auth_mode: dev` eingehängt.
"""

from typing import Final

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from loguru import logger

from portal.auth.redirects import sanitize_next
from portal.web.deps import PortalDep, SessionWriteServiceDep

router: Final = APIRouter(tags=["Entwicklung"])


@router.get("/login", response_class=HTMLResponse)
def login_picker(request: Request, portal: PortalDep, next: str | None = None) -> Response:
    """Auswahl der Testpersonen.

    :param request: Injiziertes Request-Objekt von FastAPI bzw. Starlette
    :param portal: Injizierter Portal-Kontext
    :param next: Zielpfad nach der Anmeldung
    :return: Response mit der Auswahlseite
    :rtype: Response
    """
    logger.debug("next={}", next)
    return portal.views.page(
        request,
        "pages/dev_login.html",
        title=portal.t("login.title"),
        session=None,
        users=list(portal.dev_users.values()),
        next=sanitize_next(next),
    )


@router.post("/login")
def login(
    portal: PortalDep,
    service: SessionWriteServiceDep,
    user: str = Form(...),
    next: str = Form("/"),
) -> Response:
    """Anmelden als Testperson.

    :param portal: Injizierter Portal-Kontext
    :param service: Injizierter Service für Geschäftslogik
    :param user: ID der Testperson
    :param next: Zielpfad nach der Anmeldung
    :return: Redirect auf den Zielpfad mit Session-Cookie
    :rtype: Response
    :raises UnknownUserError: Falls die Testperson nicht existiert
    """
    logger.debug("user={}", user)
    session: Final = service.create(user)
    response: Final = RedirectResponse(sanitize_next(next), status_code=303)
    response.set_cookie(
        portal.cfg.session_cookie, session.sid, httponly=True, samesite="lax", path="/"
    )
    return response
