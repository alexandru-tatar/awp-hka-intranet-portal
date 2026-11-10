"""Read-only service API over the portal's existing registry (no user session)."""
from pathlib import Path
import re
import secrets

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse


def create_registry_router(registry, token_file: Path, app_service=None, verifier=None) -> APIRouter:
    token = token_file.read_text(encoding="ascii").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{43,128}", token) is None:
        raise ValueError("Registry service token must be 43–128 base64url characters")
    expected = token.encode("ascii")
    router = APIRouter(include_in_schema=False)

    @router.get("/internal/apps/{slug}/access")
    def access(slug: str, request: Request):
        # Never accept session cookies or X-Portal-Assertion as service credentials.
        values = request.headers.getlist("authorization")
        scheme, _, supplied = values[0].partition(" ") if len(values) == 1 else ("", "", "")
        if scheme.lower() != "bearer" or not secrets.compare_digest(supplied.encode("utf-8"), expected):
            return JSONResponse({"detail": "Service authentication required"}, status_code=401,
                                headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"})
        app = registry.snapshot().get(slug)
        if app is None:
            return JSONResponse({"detail": "App not found"}, status_code=404,
                                headers={"Cache-Control": "no-store"})
        return JSONResponse({"slug": app.slug, "roles": sorted(app.roles), "status": app.status,
                             "adapters": list(app.adapters)}, headers={"Cache-Control": "no-store"})


    if verifier is not None:
        @router.post("/internal/apps/{slug}/authorize")
        def authorize(slug: str, request: Request):
            import httpx
            import jwt
            from portal.service.exceptions import ForbiddenError, NotFoundError, UnavailableError

            values = request.headers.getlist("authorization")
            scheme, _, supplied = values[0].partition(" ") if len(values) == 1 else ("", "", "")
            if scheme.lower() != "bearer" or not secrets.compare_digest(supplied.encode("utf-8"), expected):
                return JSONResponse({"error": "service_authentication"}, status_code=401, headers={"Cache-Control": "no-store"})
            assertions = request.headers.getlist("x-portal-assertion")
            try:
                user = verifier.verify(assertions[0] if len(assertions) == 1 else None)
            except (ValueError, TypeError, KeyError, jwt.PyJWTError, httpx.HTTPError):
                return JSONResponse({"error": "invalid_assertion"}, status_code=401, headers={"Cache-Control": "no-store"})
            try:
                app = app_service.find_authorized(slug, user)
            except (ForbiddenError, NotFoundError, UnavailableError) as exc:
                status, reason = (403, "forbidden") if isinstance(exc, ForbiddenError) else (
                    (404, "not_found") if isinstance(exc, NotFoundError) else (503, "unavailable"))
                return JSONResponse({"slug": slug, "allowed": False, "reason": reason}, status_code=status,
                                    headers={"Cache-Control": "no-store"})
            return JSONResponse({"slug": app.slug, "allowed": True, "adapters": list(app.adapters)},
                                headers={"Cache-Control": "no-store"})

    return router
