"""OidcRouter: Anmeldung per OIDC, /login und /oidc/callback (02 §4).

Wird nur bei `auth_mode: oidc` eingehängt.
"""

from typing import Final

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response
from loguru import logger

from portal.web.deps import LoginServiceDep, PortalDep

router: Final = APIRouter(tags=["Authentifizierung"])


@router.get("/login")
def login(portal: PortalDep, service: LoginServiceDep, next: str | None = None) -> Response:
    """Login starten: Transaktion anlegen und zum IdP weiterleiten.

    :param portal: Injizierter Portal-Kontext
    :param service: Injizierter Service für Geschäftslogik
    :param next: Zielpfad nach der Anmeldung
    :return: Redirect zum IdP mit Login-Cookie
    :rtype: Response
    :raises LoginFailedError: Falls der IdP nicht erreichbar ist
    """
    logger.debug("next={}", next)
    started: Final = service.start(next)
    response: Final = RedirectResponse(started.url, status_code=302)
    response.set_cookie(
        portal.cfg.login_cookie,
        started.lid,
        max_age=portal.cfg.login_state_ttl_seconds,
        httponly=True,
        secure=portal.cfg.cookie_secure,
        samesite="lax",
        path="/",
    )
    return response


@router.get("/oidc/callback")
def callback(
    request: Request,
    portal: PortalDep,
    service: LoginServiceDep,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> Response:
    """Callback des IdP: Session anlegen und zum Zielpfad weiterleiten.

    :param request: Injiziertes Request-Objekt von FastAPI bzw. Starlette
    :param portal: Injizierter Portal-Kontext
    :param service: Injizierter Service für Geschäftslogik
    :param code: Authorization Code des IdP
    :param state: State der Login-Transaktion
    :param error: Fehlercode des IdP
    :return: Redirect zum Zielpfad mit Session-Cookie
    :rtype: Response
    :raises LoginFailedError: Falls die Anmeldung nicht abgeschlossen werden kann
    """
    cfg: Final = portal.cfg
    finished: Final = service.finish(
        lid=request.cookies.get(cfg.login_cookie),
        code=code,
        state=state,
        idp_error=error,
        old_sid=request.cookies.get(cfg.session_cookie),
    )
    response: Final = RedirectResponse(finished.next, status_code=302)
    response.set_cookie(
        cfg.session_cookie,
        finished.session.sid,
        httponly=True,
        secure=cfg.cookie_secure,
        samesite="lax",
        path="/",
    )
    response.delete_cookie(cfg.login_cookie, path="/")
    return response
