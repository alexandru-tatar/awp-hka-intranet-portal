"""PageRouter: Startseite, Status, Verbindungen und Fehlerseiten (04 §2)."""

from typing import Final

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response
from loguru import logger

from portal.web.deps import AdminSession, AppServiceDep, CurrentSession, PortalDep
from portal.web.errors import render_error

router: Final = APIRouter(tags=["Seiten"])


@router.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    portal: PortalDep,
    service: AppServiceDep,
    session: CurrentSession,
) -> Response:
    """Startseite mit den Apps der angemeldeten Rollen.

    :param request: Injiziertes Request-Objekt von FastAPI bzw. Starlette
    :param portal: Injizierter Portal-Kontext
    :param service: Injizierter Service für Geschäftslogik
    :param session: Angemeldete Session
    :return: Response mit der Startseite
    :rtype: Response
    """
    logger.debug("sub={}", session.sub)
    groups: Final = service.find_nav_groups(session.roles)
    return portal.views.page(
        request, "pages/home.html", title=portal.t("home.title"), session=session, groups=groups
    )


@router.get("/_portal/status", response_class=HTMLResponse)
def status(
    request: Request,
    portal: PortalDep,
    service: AppServiceDep,
    session: AdminSession,
) -> Response:
    """Statusseite aller Apps, nur für platform-admin.

    :param request: Injiziertes Request-Objekt von FastAPI bzw. Starlette
    :param portal: Injizierter Portal-Kontext
    :param service: Injizierter Service für Geschäftslogik
    :param session: Session mit Rolle platform-admin
    :return: Response mit der Statusseite
    :rtype: Response
    """
    logger.debug("sub={}", session.sub)
    apps: Final = service.find_all()
    return portal.views.page(
        request, "pages/status.html", title=portal.t("status.title"), session=session, apps=apps
    )


@router.get("/_portal/connections", response_class=HTMLResponse)
def connections(request: Request, portal: PortalDep, session: CurrentSession) -> Response:
    """Seite mit den Verbindungen des Benutzers.

    :param request: Injiziertes Request-Objekt von FastAPI bzw. Starlette
    :param portal: Injizierter Portal-Kontext
    :param session: Angemeldete Session
    :return: Response mit der Verbindungsseite
    :rtype: Response
    """
    logger.debug("sub={}", session.sub)
    return portal.views.page(
        request, "pages/connections.html", title=portal.t("connections.title"), session=session
    )


@router.get("/_portal/error/{status_code}", response_class=HTMLResponse)
def error(request: Request, status_code: int) -> Response:
    """Body für die errors-Middleware von Traefik; antwortet mit dem angefragten Status.

    :param request: Injiziertes Request-Objekt von FastAPI bzw. Starlette
    :param status_code: Angefragter HTTP-Status, außerhalb 400-599 wird 404 verwendet
    :return: Response mit der Fehlerseite
    :rtype: Response
    """
    logger.debug("status_code={}", status_code)
    return render_error(request, status_code if 400 <= status_code <= 599 else 404)
