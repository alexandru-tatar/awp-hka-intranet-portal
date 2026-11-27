"""DocsRouter: Dokumentation unter ``/_portal/docs`` lesen, bearbeiten und Dateien hochladen.

Lesen dürfen die Rollen aus ``docs.read_roles`` und ``docs.edit_roles``, ändern nur ``docs.edit_roles``. Die
Schnittstelle unter ``/_portal/docs/api`` spricht JSON; ändernde Anfragen brauchen das CSRF-Token der Session im
Header ``X-CSRF-Token``.
"""

from typing import Final

from fastapi import APIRouter, Body, Header, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from loguru import logger

from portal.service import (
    ConflictError,
    DocsReadOnlyError,
    InvalidCsrfError,
    InvalidInputError,
    NotFoundError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
)
from portal.web.deps import (
    DocServiceDep,
    DocsEditor,
    DocsReader,
    DocWriteServiceDep,
    PortalDep,
    can_edit_docs,
    check_csrf,
)
from portal.web.docs_page import docs_csp

router: Final = APIRouter(prefix="/_portal/docs", tags=["Dokumentation"])

X_CSRF: Final = "X-CSRF-Token"
ASSET_CACHE: Final = "private, max-age=31536000, immutable"
_ASSET_TYPES: Final = {"png": "image/png", "jpg": "image/jpeg", "gif": "image/gif", "webp": "image/webp",
                       "pdf": "application/pdf"}


@router.get("", response_class=HTMLResponse)
def docs(portal: PortalDep, service: DocServiceDep, session: DocsReader) -> Response:
    """Dokumentation mit allen Seiten, dem Versionsverlauf und, für Bearbeitende, dem Editor.

    :param portal: Injizierter Portal-Kontext
    :param service: Lesender Service der Dokumentation
    :param session: Session mit Lese- oder Bearbeitungsrolle
    :return: Die Seite mit eigener Content-Security-Policy
    :rtype: Response
    """
    logger.debug("sub={}", session.sub)
    html, nonce = portal.docs_page.render(
        pages=service.find_all(), changes=service.find_changes(), session=session,
        can_edit=can_edit_docs(portal.cfg.docs, session), writable=service.writable,
        max_upload_bytes=portal.cfg.docs.max_upload_bytes,
    )
    return HTMLResponse(html, headers={"Content-Security-Policy": docs_csp(nonce)})


@router.get("/assets/{name}")
def asset(name: str, service: DocServiceDep, session: DocsReader) -> Response:
    """Hochgeladenes Bild oder PDF.

    :param name: Dateiname
    :param service: Lesender Service der Dokumentation
    :param session: Session mit Lese- oder Bearbeitungsrolle
    :return: Die Datei; PDFs als Download
    :rtype: Response
    :raises NotFoundError: Falls es die Datei nicht gibt
    """
    logger.debug("name={}", name)
    path = service.find_asset(name)
    ext = path.suffix[1:]
    headers = {"Cache-Control": ASSET_CACHE, "Content-Security-Policy": "default-src 'none'; sandbox"}
    return FileResponse(path, media_type=_ASSET_TYPES[ext], headers=headers,
                        content_disposition_type="attachment" if ext == "pdf" else "inline",
                        filename=name if ext == "pdf" else None)


@router.get("/api/pages")
def list_pages(service: DocServiceDep, session: DocsReader) -> Response:
    """Alle Seiten ohne Inhalt (für Links im Editor).

    :param service: Lesender Service der Dokumentation
    :param session: Session mit Lese- oder Bearbeitungsrolle
    :return: JSON ``{"pages": [...]}``
    :rtype: Response
    """
    logger.debug("sub={}", session.sub)
    return JSONResponse({"pages": [p.to_json() for p in service.find_all()]})


@router.get("/api/pages/{slug}")
def get_page(slug: str, portal: PortalDep, service: DocServiceDep, session: DocsReader) -> Response:
    """Aktueller Stand einer Seite mit Inhalt.

    :param slug: Kurzname
    :param portal: Injizierter Portal-Kontext
    :param service: Lesender Service der Dokumentation
    :param session: Session mit Lese- oder Bearbeitungsrolle
    :return: JSON der Seite oder 404
    :rtype: Response
    """
    logger.debug("slug={}", slug)
    try:
        return JSONResponse(service.find_by_slug(slug).to_json(with_html=True))
    except NotFoundError:
        return _error(portal, 404, "not_found")


@router.get("/api/pages/{slug}/history")
def history(slug: str, portal: PortalDep, service: DocServiceDep, session: DocsReader) -> Response:
    """Versionsverlauf einer Seite, die neueste zuerst.

    :param slug: Kurzname
    :param portal: Injizierter Portal-Kontext
    :param service: Lesender Service der Dokumentation
    :param session: Session mit Lese- oder Bearbeitungsrolle
    :return: JSON ``{"versions": [...]}`` oder 404
    :rtype: Response
    """
    logger.debug("slug={}", slug)
    try:
        return JSONResponse({"versions": [v.to_json() for v in service.find_history(slug)]})
    except NotFoundError:
        return _error(portal, 404, "not_found")


@router.get("/api/pages/{slug}/versions/{version}")
def version(slug: str, version: int, portal: PortalDep, service: DocServiceDep, session: DocsReader) -> Response:
    """Eine bestimmte Version mit Inhalt.

    :param slug: Kurzname
    :param version: Nummer der Version
    :param portal: Injizierter Portal-Kontext
    :param service: Lesender Service der Dokumentation
    :param session: Session mit Lese- oder Bearbeitungsrolle
    :return: JSON der Version oder 404
    :rtype: Response
    """
    logger.debug("slug={} version={}", slug, version)
    try:
        return JSONResponse(service.find_version(slug, version).to_json(with_html=True))
    except NotFoundError:
        return _error(portal, 404, "not_found")


@router.post("/api/pages")
def create_page(portal: PortalDep, service: DocWriteServiceDep, session: DocsEditor,
                payload: dict = Body(...), csrf: str = Header("", alias=X_CSRF)) -> Response:
    """Neue Seite anlegen.

    :param portal: Injizierter Portal-Kontext
    :param service: Schreibender Service der Dokumentation
    :param session: Session mit Bearbeitungsrolle
    :param payload: ``{"title", "group", "html"?, "level"?, "note"?, "after"?}``
    :param csrf: CSRF-Token aus dem Header
    :return: JSON der neuen Seite (201)
    :rtype: Response
    """
    logger.debug("sub={}", session.sub)
    return _write(portal, session, csrf, lambda: JSONResponse(service.create(
        session, title=_str(payload, "title"), group=_str(payload, "group"), html=_str(payload, "html"),
        level=_str(payload, "level"), note=_str(payload, "note"), after=_str(payload, "after") or None,
    ).to_json(), status_code=201))


@router.put("/api/pages/{slug}")
def update_page(slug: str, portal: PortalDep, service: DocWriteServiceDep, session: DocsEditor,
                payload: dict = Body(...), csrf: str = Header("", alias=X_CSRF)) -> Response:
    """Neue Version einer Seite veröffentlichen.

    :param slug: Kurzname
    :param portal: Injizierter Portal-Kontext
    :param service: Schreibender Service der Dokumentation
    :param session: Session mit Bearbeitungsrolle
    :param payload: ``{"base_version", "html", "group"?, "level"?, "note"?}``
    :param csrf: CSRF-Token aus dem Header
    :return: JSON der Seite mit der neuen Version, 409 bei einem Konflikt
    :rtype: Response
    """
    logger.debug("slug={}", slug)
    base = payload.get("base_version")
    if not isinstance(base, int):
        return _error(portal, 422, "invalid")
    return _write(portal, session, csrf, lambda: JSONResponse(service.update(
        session, slug, base_version=base, html=_str(payload, "html"),
        group=payload.get("group") if isinstance(payload.get("group"), str) else None,
        level=payload.get("level") if isinstance(payload.get("level"), str) else None,
        note=_str(payload, "note"),
    ).to_json()))


@router.post("/api/pages/{slug}/restore")
def restore_page(slug: str, portal: PortalDep, service: DocWriteServiceDep, session: DocsEditor,
                 payload: dict = Body(...), csrf: str = Header("", alias=X_CSRF)) -> Response:
    """Frühere Version als neue Version veröffentlichen.

    :param slug: Kurzname
    :param portal: Injizierter Portal-Kontext
    :param service: Schreibender Service der Dokumentation
    :param session: Session mit Bearbeitungsrolle
    :param payload: ``{"version"}``
    :param csrf: CSRF-Token aus dem Header
    :return: JSON der Seite mit der neuen Version
    :rtype: Response
    """
    logger.debug("slug={}", slug)
    number = payload.get("version")
    if not isinstance(number, int):
        return _error(portal, 422, "invalid")
    return _write(portal, session, csrf, lambda: JSONResponse(service.restore(session, slug, number).to_json()))


@router.delete("/api/pages/{slug}")
def delete_page(slug: str, portal: PortalDep, service: DocWriteServiceDep, session: DocsEditor,
                csrf: str = Header("", alias=X_CSRF)) -> Response:
    """Seite löschen; der Versionsverlauf bleibt erhalten.

    :param slug: Kurzname
    :param portal: Injizierter Portal-Kontext
    :param service: Schreibender Service der Dokumentation
    :param session: Session mit Bearbeitungsrolle
    :param csrf: CSRF-Token aus dem Header
    :return: 204 ohne Inhalt
    :rtype: Response
    """
    logger.debug("slug={}", slug)

    def run() -> Response:
        service.delete(session, slug)
        return Response(status_code=204)

    return _write(portal, session, csrf, run)


@router.post("/api/assets")
async def upload_asset(request: Request, portal: PortalDep, service: DocWriteServiceDep, session: DocsEditor,
                       csrf: str = Header("", alias=X_CSRF)) -> Response:
    """Bild (PNG, JPEG, GIF, WebP) oder PDF hochladen; der Inhalt ist der Anfrage-Body.

    :param request: Anfrage; ``Content-Type`` nennt das Format
    :param portal: Injizierter Portal-Kontext
    :param service: Schreibender Service der Dokumentation
    :param session: Session mit Bearbeitungsrolle
    :param csrf: CSRF-Token aus dem Header
    :return: JSON ``{"url"}`` (201)
    :rtype: Response
    """
    logger.debug("sub={}", session.sub)
    limit = service.max_upload_bytes
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit:
        return _error(portal, 413, "too_large", limit_mb=_mb(limit))
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > limit:
            return _error(portal, 413, "too_large", limit_mb=_mb(limit))
    media = request.headers.get("content-type", "")
    return _write(portal, session, csrf,
                  lambda: JSONResponse({"url": service.upload_asset(bytes(data), media)}, status_code=201))


def _write(portal, session, csrf, run) -> Response:
    try:
        check_csrf(session, csrf)
        return run()
    except InvalidCsrfError:
        return _error(portal, 400, "csrf")
    except NotFoundError:
        return _error(portal, 404, "not_found")
    except ConflictError as exc:
        return _error(portal, 409, "conflict", name=exc.updated_by,
                      extra={"current_version": exc.current_version, "updated_by": exc.updated_by})
    except InvalidInputError as exc:
        return _error(portal, 422, exc.key.removeprefix("docs_"))
    except DocsReadOnlyError:
        return _error(portal, 403, "read_only")
    except PayloadTooLargeError as exc:
        return _error(portal, 413, "too_large", limit_mb=_mb(exc.limit))
    except UnsupportedMediaTypeError:
        return _error(portal, 415, "media_type")


def _error(portal, status: int, key: str, *, extra: dict | None = None, **values) -> Response:
    message_key = f"docs.error.{key}"
    message = portal.t(message_key, **values) if message_key in portal.t else portal.t("docs.error.invalid")
    return JSONResponse({"error": key, "message": message, **(extra or {})}, status_code=status)


def _str(payload: dict, key: str) -> str:
    value = payload.get(key, "")
    return value if isinstance(value, str) else ""


def _mb(limit: int) -> str:
    return f"{limit / 1024 / 1024:.0f}"
