"""AdminRouter: Verwaltungsseite für platform-admin: Apps ansehen, entfernen, Rollen der Apps und Grants ändern."""

from typing import Final

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from loguru import logger

from portal.service import InvalidInputError
from portal.web.deps import AdminServiceDep, AdminSession, PortalDep, check_csrf

router: Final = APIRouter(prefix="/_portal/admin", tags=["Verwaltung"])

# Meldungen nach einer Änderung (Post/Redirect/Get); nur diese Schlüssel erscheinen auf der Seite.
NOTICES: Final = frozenset({"app_removed", "app_roles", "grant_set", "grant_deleted"})


def _page(request: Request, portal: PortalDep, service: AdminServiceDep, session: AdminSession, *,
          notice: str | None = None, error: str | None = None, status_code: int = 200) -> Response:
    """Die Verwaltungsseite rendern.

    :param request: Anfrage
    :param portal: Portal-Kontext
    :param service: Service der Verwaltungsseite
    :param session: Session des Admins
    :param notice: Schlüssel einer Erfolgsmeldung
    :param error: Schlüssel eines Fehlertexts
    :param status_code: HTTP-Status der Antwort
    :return: Die Seite
    :rtype: Response
    """
    return portal.views.page(
        request, "pages/admin.html", title=portal.t("admin.title"), session=session, status_code=status_code,
        apps=service.find_apps(), grants=service.find_grants(), roles=service.role_vocabulary,
        can_manage_apps=service.can_manage_apps, can_manage_grants=service.can_manage_grants,
        has_grants=service.has_grants, notice=notice if notice in NOTICES else None, error=error,
    )


@router.get("", response_class=HTMLResponse)
def admin(request: Request, portal: PortalDep, service: AdminServiceDep, session: AdminSession,
          notice: str | None = None) -> Response:
    """Verwaltungsseite: alle Apps mit Besitzer, Status und Rollen sowie die Grants je Person.

    :param request: Injiziertes Request-Objekt
    :param portal: Injizierter Portal-Kontext
    :param service: Service der Verwaltungsseite
    :param session: Session mit Rolle platform-admin
    :param notice: Schlüssel der Meldung nach einer Änderung
    :return: Die Seite
    :rtype: Response
    """
    logger.debug("sub={}", session.sub)
    return _page(request, portal, service, session, notice=notice)


@router.post("/apps/{slug}/remove")
def remove_app(slug: str, service: AdminServiceDep, session: AdminSession, csrf: str = Form("")) -> Response:
    """Eine App stilllegen.

    :param slug: Name der App
    :param service: Service der Verwaltungsseite
    :param session: Session mit Rolle platform-admin
    :param csrf: CSRF-Token aus dem Formular
    :return: Redirect auf die Verwaltungsseite
    :rtype: Response
    :raises InvalidCsrfError: Falls das CSRF-Token nicht passt
    :raises NotFoundError: Falls es die App nicht gibt
    """
    check_csrf(session, csrf)
    service.remove_app(slug, session)
    return RedirectResponse("/_portal/admin?notice=app_removed", status_code=303)


@router.post("/apps/{slug}/roles")
def set_app_roles(request: Request, slug: str, portal: PortalDep, service: AdminServiceDep, session: AdminSession,
                  csrf: str = Form(""), roles: list[str] = Form(default_factory=list)) -> Response:
    """Die Rollen einer App ändern.

    :param request: Injiziertes Request-Objekt
    :param slug: Name der App
    :param portal: Injizierter Portal-Kontext
    :param service: Service der Verwaltungsseite
    :param session: Session mit Rolle platform-admin
    :param csrf: CSRF-Token aus dem Formular
    :param roles: Gewählte Rollen
    :return: Redirect auf die Verwaltungsseite, bei ungültiger Eingabe die Seite mit Fehler (422)
    :rtype: Response
    :raises InvalidCsrfError: Falls das CSRF-Token nicht passt
    :raises NotFoundError: Falls es die App nicht gibt
    """
    check_csrf(session, csrf)
    try:
        service.set_app_roles(slug, roles, session)
    except InvalidInputError as exc:
        return _page(request, portal, service, session, error=exc.key, status_code=422)
    return RedirectResponse("/_portal/admin?notice=app_roles", status_code=303)


@router.post("/grants")
def set_grant(request: Request, portal: PortalDep, service: AdminServiceDep, session: AdminSession,
              csrf: str = Form(""), sub: str = Form(""), roles: list[str] = Form(default_factory=list)) -> Response:
    """Die zusätzlichen Rollen einer Person setzen; ohne Rollen entfällt der Eintrag.

    :param request: Injiziertes Request-Objekt
    :param portal: Injizierter Portal-Kontext
    :param service: Service der Verwaltungsseite
    :param session: Session mit Rolle platform-admin
    :param csrf: CSRF-Token aus dem Formular
    :param sub: Subject der Person im IdP
    :param roles: Gewählte Rollen
    :return: Redirect auf die Verwaltungsseite, bei ungültiger Eingabe die Seite mit Fehler (422)
    :rtype: Response
    :raises InvalidCsrfError: Falls das CSRF-Token nicht passt
    """
    check_csrf(session, csrf)
    try:
        service.set_grant(sub, roles, session)
    except InvalidInputError as exc:
        return _page(request, portal, service, session, error=exc.key, status_code=422)
    return RedirectResponse("/_portal/admin?notice=grant_set", status_code=303)


@router.post("/grants/delete")
def delete_grant(service: AdminServiceDep, session: AdminSession, csrf: str = Form(""),
                 sub: str = Form("")) -> Response:
    """Die zusätzlichen Rollen einer Person löschen.

    :param service: Service der Verwaltungsseite
    :param session: Session mit Rolle platform-admin
    :param csrf: CSRF-Token aus dem Formular
    :param sub: Subject der Person im IdP
    :return: Redirect auf die Verwaltungsseite
    :rtype: Response
    :raises InvalidCsrfError: Falls das CSRF-Token nicht passt
    :raises NotFoundError: Falls es für das Subject keinen Eintrag gibt
    """
    check_csrf(session, csrf)
    service.delete_grant(sub, session)
    return RedirectResponse("/_portal/admin?notice=grant_deleted", status_code=303)
