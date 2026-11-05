"""AppRouter: ``/apps/<slug>/…`` an den Container der App weiterleiten (HKA-52, 02 §6)."""

from typing import Final

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response
from loguru import logger

from portal.service import ForbiddenError
from portal.web.deps import AppServiceDep, AssertionServiceDep, OptionalSession, PortalDep
from portal.web.proxy import is_same_origin

router: Final = APIRouter(tags=["Apps"])

SAFE_METHODS: Final = frozenset({"GET", "HEAD", "OPTIONS"})


@router.get("/apps/{slug}")
def add_trailing_slash(slug: str) -> Response:
    """Redirect auf den Pfad mit abschließendem Slash.

    :param slug: Slug der App
    :return: Permanenter Redirect (308) auf ``/apps/<slug>/``
    :rtype: Response
    """
    return RedirectResponse(f"/apps/{slug}/", status_code=308)


@router.api_route(
    "/apps/{slug}/{path:path}",
    methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    include_in_schema=False,
)
async def forward_to_app(
    request: Request,
    portal: PortalDep,
    service: AppServiceDep,
    assertions: AssertionServiceDep,
    session: OptionalSession,
    slug: str,
    path: str,
) -> Response:
    """Zugriff prüfen, Token ausstellen und die Anfrage an die App weitergeben.

    Reihenfolge wie bei ``/auth/verify``: unbekannt, Anmeldung, Rolle, Status. Eine abgewiesene Anfrage erreicht die
    App nie.

    :param request: Injiziertes Request-Objekt von FastAPI bzw. Starlette
    :param portal: Injizierter Portal-Kontext
    :param service: Injizierter Service für Geschäftslogik
    :param assertions: Injizierter Service für Identitäts-Tokens
    :param session: Angemeldete Session oder None
    :param slug: Slug der App
    :param path: Rest des Pfads unter ``/apps/<slug>/``
    :return: Antwort der App
    :rtype: Response
    :raises NotFoundError: Falls die App unbekannt oder nicht geroutet ist
    :raises LoginRequiredError: Falls keine Session vorhanden ist
    :raises ForbiddenError: Falls keine passende Rolle vorhanden ist oder die Anfrage von einer fremden Seite stammt
    :raises UnavailableError: Falls die App nicht gesund oder nicht erreichbar ist
    """
    logger.debug("slug={} path={}", slug, path)
    app = service.find_authorized(slug, session)
    assert session is not None and portal.proxy is not None  # find_authorized wirft ohne Session; apps-Abschnitt gesetzt
    if request.method not in SAFE_METHODS and not is_same_origin(request):
        raise ForbiddenError(slug)
    return await portal.proxy.forward(request, slug, assertions.mint(session, app))
