"""LanguageRouter: Sprachwechsel Deutsch/Englisch (HKA-101).

Wird nur bei `auth_mode: dev` eingehängt. Hinter dem Security-Gateway speichert das Gateway die Wahl
(es entfernt Cookies auf dem Weg zum Portal) und reicht sie als ``Accept-Language`` weiter.
"""

from typing import Final

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse, Response
from loguru import logger

from portal.auth.redirects import sanitize_local_path
from portal.core.i18n import LANGUAGE_COOKIE, LANGUAGES
from portal.web.deps import PortalDep

router: Final = APIRouter(tags=["Sprache"])

ONE_YEAR: Final = 365 * 24 * 3600


@router.get("/sprache/{code}")
def set_language(code: str, portal: PortalDep, next: str | None = None) -> Response:
    """Sprache merken und zur vorherigen Seite zurückkehren.

    :param code: ``de`` oder ``en``
    :param portal: Injizierter Portal-Kontext
    :param next: Pfad der Seite, zu der die Person zurückkehrt; Fremdes ergibt ``/``
    :return: Redirect (303) mit dem Cookie ``hka_lang``
    :rtype: Response
    :raises HTTPException: 404, falls ``code`` keine unterstützte Sprache ist
    """
    if code not in LANGUAGES:
        raise HTTPException(status_code=404)
    logger.debug("code={} next={}", code, next)
    response: Final = RedirectResponse(sanitize_local_path(next), status_code=303)
    response.set_cookie(
        LANGUAGE_COOKIE, code, max_age=ONE_YEAR, httponly=True, samesite="lax", path="/",
        secure=portal.cfg.cookie_secure,
    )
    return response
