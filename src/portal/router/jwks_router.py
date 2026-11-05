"""JwksRouter: ``GET /.well-known/jwks.json``, die öffentlichen Schlüssel für Apps (02 §7)."""

from typing import Final

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from loguru import logger

from portal.router.constants import CACHE_CONTROL, JWKS_MAX_AGE
from portal.web.deps import PortalDep

router: Final = APIRouter(tags=["Schlüssel"])


@router.get("/.well-known/jwks.json")
def jwks(portal: PortalDep) -> Response:
    """Öffentliche Schlüssel (aktuell, nächster, voriger) als JWKS.

    :param portal: Injizierter Portal-Kontext
    :return: JWKS mit ``Cache-Control: public, max-age=300``, 404 ohne Abschnitt ``assertion``
    :rtype: Response
    """
    logger.debug("keys={}", portal.keys is not None)
    if portal.keys is None:
        return Response(status_code=404)
    return JSONResponse(portal.keys.jwks(), headers={CACHE_CONTROL: JWKS_MAX_AGE})
