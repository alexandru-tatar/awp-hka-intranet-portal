"""Test-Anmeldung für den Entwicklungsmodus (06 §7). Im Betrieb nie aktiv."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from typing import TYPE_CHECKING

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .context import User
from .pages import env

if TYPE_CHECKING:
    from .portal import Portal

COOKIE = "portal_dev"
_KEY = secrets.token_bytes(32)  # neu bei jedem Start: alte Test-Anmeldungen verfallen

TEST_PERSONS = [
    {"sub": "student-test", "name": "Erika Musterfrau", "hint": "mit Noten"},
    {"sub": "student-empty", "name": "Max Mustermann", "hint": "ohne Noten"},
]


def _sign(data: bytes) -> str:
    return hmac.new(_KEY, data, hashlib.sha256).hexdigest()


def user_from_cookie(request: Request) -> User | None:
    raw = request.cookies.get(COOKIE, "")
    payload, _, signature = raw.partition(".")
    if not payload or not hmac.compare_digest(_sign(payload.encode()), signature):
        return None
    data = json.loads(base64.urlsafe_b64decode(payload))
    return User(sub=data["sub"], name=data["name"], roles=tuple(data["roles"]), email=data.get("email"))


def router(portal: Portal) -> APIRouter:
    r = APIRouter(prefix="/__dev", include_in_schema=False)
    manifest_roles = portal.manifest["roles"]

    @r.get("/login", response_class=HTMLResponse)
    async def login_form() -> str:
        return env.get_template("dev_login.html").render(
            persons=TEST_PERSONS, roles=manifest_roles, app=portal.manifest["name"]
        )

    @r.post("/login")
    async def login(request: Request) -> RedirectResponse:
        form = await request.form()
        person = next((p for p in TEST_PERSONS if p["sub"] == form.get("sub")), TEST_PERSONS[0])
        roles = [str(v) for v in form.getlist("roles")]
        roles += [x for x in str(form.get("extra_roles", "")).replace(",", " ").split() if x not in roles]
        payload = base64.urlsafe_b64encode(
            json.dumps({"sub": person["sub"], "name": person["name"], "roles": roles}).encode()
        ).decode()
        response = RedirectResponse(portal.base_path or "/", status_code=303)
        response.set_cookie(COOKIE, f"{payload}.{_sign(payload.encode())}", httponly=True, samesite="lax")
        return response

    return r
