"""DevRouter: Platzhalter-Apps statt Traefik-Routing.

Wird nur bei `env: dev` eingehängt.
"""

from typing import Final

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from loguru import logger

from portal.context import Portal
from portal.service import AppDTO, SessionDTO
from portal.web.deps import AppServiceDep, OptionalSession, PortalDep

router: Final = APIRouter(tags=["Entwicklung"])


@router.get("/apps/{slug}/", response_class=HTMLResponse)
def placeholder_app(
    request: Request,
    portal: PortalDep,
    service: AppServiceDep,
    session: OptionalSession,
    slug: str,
) -> Response:
    """Platzhalter-Seite einer App mit den Mustern des Kits.

    :param request: Injiziertes Request-Objekt von FastAPI bzw. Starlette
    :param portal: Injizierter Portal-Kontext
    :param service: Injizierter Service für Geschäftslogik
    :param session: Angemeldete Session oder None
    :param slug: Slug der App
    :return: Response mit der Platzhalter-Seite
    :rtype: Response
    :raises NotFoundError: Falls die App unbekannt oder nicht geroutet ist
    :raises LoginRequiredError: Falls keine Session vorhanden ist
    :raises ForbiddenError: Falls keine passende Rolle vorhanden ist
    :raises UnavailableError: Falls die App nicht gesund ist
    """
    logger.debug("slug={}", slug)
    app, session = _authorize_app(service, slug, session)
    return _render_app(request, portal, app, session)


@router.post("/apps/{slug}/", response_class=HTMLResponse)
def placeholder_app_submit(
    request: Request,
    portal: PortalDep,
    service: AppServiceDep,
    session: OptionalSession,
    slug: str,
    subject: str = Form(""),
) -> Response:
    """Formular der Platzhalter-Seite absenden.

    :param request: Injiziertes Request-Objekt von FastAPI bzw. Starlette
    :param portal: Injizierter Portal-Kontext
    :param service: Injizierter Service für Geschäftslogik
    :param session: Angemeldete Session oder None
    :param slug: Slug der App
    :param subject: Betreff aus dem Formular
    :return: Response mit der Seite samt Bestätigung bzw. Fehlermeldung
    :rtype: Response
    :raises NotFoundError: Falls die App unbekannt oder nicht geroutet ist
    :raises LoginRequiredError: Falls keine Session vorhanden ist
    :raises ForbiddenError: Falls keine passende Rolle vorhanden ist
    :raises UnavailableError: Falls die App nicht gesund ist
    """
    logger.debug("slug={}", slug)
    app, session = _authorize_app(service, slug, session)
    return _render_app(request, portal, app, session, submitted=True, subject=subject.strip())


@router.get("/apps/{slug}")
def add_trailing_slash(slug: str) -> Response:
    """Redirect auf den Pfad mit abschließendem Slash.

    :param slug: Slug der App
    :return: Permanenter Redirect (308) auf ``/apps/<slug>/``
    :rtype: Response
    """
    return RedirectResponse(f"/apps/{slug}/", status_code=308)


def _authorize_app(
    service: AppServiceDep, slug: str, session: SessionDTO | None
) -> tuple[AppDTO, SessionDTO]:
    """Zugriff auf eine App prüfen und App samt Session liefern.

    :param service: App-Service
    :param slug: Slug der App
    :param session: Session oder ``None``
    :return: App und Session
    :rtype: tuple[AppDTO, SessionDTO]
    :raises NotFoundError: Falls die App unbekannt oder nicht geroutet ist
    :raises LoginRequiredError: Falls keine Session vorhanden ist
    :raises ForbiddenError: Falls keine passende Rolle vorhanden ist
    :raises UnavailableError: Falls die App nicht gesund ist
    """
    app: Final = service.find_authorized(slug, session)
    assert session is not None  # find_authorized wirft sonst LoginRequiredError
    return app, session


def _render_app(
    request: Request,
    portal: Portal,
    app: AppDTO,
    session: SessionDTO,
    *,
    submitted: bool = False,
    subject: str = "",
) -> Response:
    """Platzhalter-Seite einer App rendern.

    :param request: Anfrage
    :param portal: Portal-Kontext
    :param app: App
    :param session: Session
    :param submitted: Ob das Formular abgeschickt wurde
    :param subject: Betreff aus dem Formular
    :return: Die Seite
    :rtype: Response
    """
    return portal.views.page(
        request,
        "pages/dev_app.html",
        title=app.name,
        session=session,
        current=app.path,
        app=app,
        submitted=submitted,
        subject=subject,
        subject_error=submitted and not subject,
    )
