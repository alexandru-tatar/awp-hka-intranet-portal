"""NavRouter: GET /nav, das Menü-Fragment für layout() des SDK (04 §7.1, §8)."""

import hashlib
from typing import Final

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response
from loguru import logger

from portal.router.constants import (
    CACHE_CONTROL,
    ETAG,
    IF_NONE_MATCH,
    NAV_MAX_AGE,
    UNAUTHORIZED,
    X_PORTAL_KIT,
)
from portal.web.deps import OptionalSession, PortalDep

router: Final = APIRouter(tags=["Navigation"])


@router.get("/nav")
def nav(
    request: Request,
    portal: PortalDep,
    session: OptionalSession,
    current: str | None = None,
) -> Response:
    """Menü-Fragment mit ETag und If-None-Match.

    Im echten Gateway kommt die Anfrage über den Apps-Listener mit
    `Authorization: Bearer <assertion>`; in Dev ersetzt das Session-Cookie die Assertion.

    :param request: Injiziertes Request-Objekt von FastAPI bzw. Starlette
    :param portal: Injizierter Portal-Kontext
    :param session: Angemeldete Session oder None
    :param current: Pfad der aktuellen Seite zum Markieren des Menüeintrags
    :return: Response mit dem Fragment, 304 bei passendem ETag, 401 ohne Session
    :rtype: Response
    """
    logger.debug("current={}", current)
    if session is None:
        return Response(UNAUTHORIZED, status_code=401, media_type="application/problem+json")

    body: Final = str(portal.views.nav_html(session, current))
    etag: Final = _etag_for(portal.kit.id, body)
    headers: Final = {
        ETAG: etag,
        CACHE_CONTROL: NAV_MAX_AGE,
        X_PORTAL_KIT: portal.kit.id,
    }
    if request.headers.get(IF_NONE_MATCH) == etag:
        return Response(status_code=304, headers=headers)
    return HTMLResponse(body, headers=headers)


def _etag_for(kit_id: str, body: str) -> str:
    """ETag des Menüs; ändert sich mit dem Menü und mit jedem Kit-Release.

    :param kit_id: Kennung des Kits
    :param body: HTML des Menüs
    :return: ETag in Anführungszeichen
    :rtype: str
    """
    return '"' + hashlib.sha256(f"{kit_id}\n{body}".encode()).hexdigest()[:20] + '"'
