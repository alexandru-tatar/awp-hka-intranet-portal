"""AppCreationRouter: neue App anlegen, als Portal-Seite und als JSON-Schnittstelle (HKA-82).

Beide Eingänge rufen denselben :class:`~portal.service.AppCreationService`. Die Seite liegt unter
``/_portal/neue-app``, die Schnittstelle unter ``/_portal/api/apps``. Die Schnittstelle antwortet immer mit JSON,
nie mit einer HTML-Fehlerseite, und nennt weder Token noch Schlüssel.
"""

from typing import Final

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from loguru import logger
from starlette.concurrency import run_in_threadpool

from portal.service import (
    AppCreationFailedError,
    CreateAppRequest,
    InvalidAppRequestError,
    InvalidCsrfError,
    NotAllowedError,
    SlugTakenError,
)
from portal.web.deps import AppCreationServiceDep, CurrentSession, PortalDep, check_csrf, optional_session

router: Final = APIRouter(prefix="/_portal", tags=["Neue App"])

NO_STORE: Final = {"Cache-Control": "no-store"}


def _page(request: Request, portal: PortalDep, session: CurrentSession, *, status_code: int = 200,
          values: dict[str, str] | None = None, errors: list[tuple[str, str]] | None = None) -> Response:
    """Das Formular rendern.

    :param request: Anfrage
    :param portal: Portal-Kontext
    :param session: Session der Person
    :param status_code: HTTP-Status der Antwort
    :param values: Eingegebene Werte, ``slug``, ``language`` und ``github_login``
    :param errors: Fehler als Paare aus Feld-ID und Text
    :return: Die Seite
    :rtype: Response
    """
    return portal.views.page(
        request, "pages/neue_app.html", title=portal.t("neue_app.title"), session=session, status_code=status_code,
        values={"slug": "", "language": "python", "github_login": "", **(values or {})}, errors=errors or [],
        result=None,
    )


@router.get("/neue-app", response_class=HTMLResponse)
def form(request: Request, portal: PortalDep, service: AppCreationServiceDep, session: CurrentSession) -> Response:
    """Das Formular zum Anlegen einer App.

    :param request: Injiziertes Request-Objekt
    :param portal: Injizierter Portal-Kontext
    :param service: Service zum Anlegen
    :param session: Angemeldete Session
    :return: Die Seite
    :rtype: Response
    :raises NotAllowedError: Falls die Person keine Rolle aus ``creator_roles`` hat (403)
    """
    service.check_allowed(session)
    return _page(request, portal, session)


@router.post("/neue-app", response_class=HTMLResponse)
def submit(request: Request, portal: PortalDep, service: AppCreationServiceDep, session: CurrentSession,
           csrf: str = Form(""), slug: str = Form(""), language: str = Form(""),
           github_login: str = Form("")) -> Response:
    """Die App anlegen und das Ergebnis zeigen.

    :param request: Injiziertes Request-Objekt
    :param portal: Injizierter Portal-Kontext
    :param service: Service zum Anlegen
    :param session: Angemeldete Session
    :param csrf: CSRF-Token aus dem Formular
    :param slug: Kurzname der App
    :param language: ``python`` oder ``js``
    :param github_login: GitHub-Name der Person, die eingeladen wird
    :return: Die Ergebnisseite, bei Fehlern das Formular mit Fehlerliste (422, 409) oder die Fehlerseite (502)
    :rtype: Response
    :raises InvalidCsrfError: Falls das CSRF-Token nicht passt
    :raises NotAllowedError: Falls die Rolle fehlt (403)
    """
    check_csrf(session, csrf)
    t = portal.t
    values = {"slug": slug.strip(), "language": language, "github_login": github_login.strip()}
    try:
        created = service.create(CreateAppRequest(**values), session)
    except InvalidAppRequestError as exc:
        field_id = {"slug": "slug", "language": "language-python", "github_login": "github-login"}[exc.field]
        return _page(request, portal, session, status_code=422, values=values,
                     errors=[(field_id, t(f"neue_app.error.{exc.key}"))])
    except SlugTakenError:
        return _page(request, portal, session, status_code=409, values=values,
                     errors=[("slug", t("neue_app.error.slug_taken"))])
    except AppCreationFailedError as exc:
        step = t(f"neue_app.step.{exc.step}") if f"neue_app.step.{exc.step}" in t else exc.step
        key = "failed_after" if exc.created else "failed_before"
        text = t(f"neue_app.error.{key}", step=step, repo=exc.repo or "", request_id=request.state.request_id)
        return _page(request, portal, session, status_code=502, values=values, errors=[("neue-app-form", text)])
    response = portal.views.page(
        request, "pages/neue_app.html", title=t("neue_app.done.title"), session=session, status_code=200,
        values=values, errors=[], result=created,
    )
    response.headers.update(NO_STORE)
    return response


def _json(status: int, **body: object) -> JSONResponse:
    """Eine JSON-Antwort ohne Zwischenspeicher.

    :param status: HTTP-Status
    :param body: Felder der Antwort
    :return: Die Antwort
    :rtype: JSONResponse
    """
    return JSONResponse(body, status_code=status, headers=NO_STORE)


@router.post("/api/apps")
async def create_api(request: Request, portal: PortalDep) -> Response:
    """Eine App anlegen (JSON). Nutzlast ``{"slug", "language", "github_login"}``, Header ``X-CSRF-Token``.

    Antworten: 201 ``{"slug", "repo", "url"}``; 401 ``login_required``; 403 ``forbidden`` oder ``csrf``;
    404 ``disabled``; 409 ``slug_taken``; 422 ``invalid`` mit ``field`` und ``reason``; 502 ``failed`` mit
    ``step``, ``created``, ``repo`` und ``url``.

    :param request: Injiziertes Request-Objekt
    :param portal: Injizierter Portal-Kontext
    :return: JSON-Antwort
    :rtype: Response
    """
    service = portal.app_creation_service
    if service is None:
        return _json(404, error="disabled")
    session = optional_session(request, portal)
    if session is None:
        return _json(401, error="login_required")
    try:
        check_csrf(session, request.headers.get("x-csrf-token", ""))
    except InvalidCsrfError:
        return _json(403, error="csrf")
    try:
        service.check_allowed(session)
    except NotAllowedError:
        return _json(403, error="forbidden")
    try:
        body = await request.json()
    except ValueError:
        body = None
    if not isinstance(body, dict) or set(body) - {"slug", "language", "github_login"} or not all(
            isinstance(body.get(key), str) for key in ("slug", "language", "github_login")):
        return _json(422, error="invalid", field="body", reason="body")
    try:
        created = await run_in_threadpool(service.create, CreateAppRequest(
            slug=body["slug"].strip(), language=body["language"], github_login=body["github_login"].strip()), session)
    except InvalidAppRequestError as exc:
        return _json(422, error="invalid", field=exc.field, reason=exc.key)
    except SlugTakenError:
        return _json(409, error="slug_taken")
    except NotAllowedError:
        return _json(403, error="forbidden")
    except AppCreationFailedError as exc:
        logger.warning("api_app_creation_failed step={} created={}", exc.step, exc.created)
        return _json(502, error="failed", step=exc.step, created=exc.created, repo=exc.repo, url=exc.url)
    return _json(201, slug=created.slug, repo=created.repo, url=created.url)
