"""HealthRouter: /readyz prüft Redis (02 §10); Compose und Traefik nutzen es als Healthcheck."""

from typing import Final

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response

from portal.web.deps import PortalDep

router: Final = APIRouter(tags=["Betrieb"])


@router.get("/readyz")
def readyz(portal: PortalDep) -> Response:
    """Bereitschaft des Portals.

    :param portal: Injizierter Portal-Kontext
    :return: 200, oder 503 mit dem fehlgeschlagenen Check
    :rtype: Response
    """
    if not portal.session_store.ping():
        return JSONResponse({"status": "unavailable", "check": "redis"}, status_code=503)
    return JSONResponse({"status": "ok"})
