"""Fehlerantworten des SDK: HTML-Seite für Browser, sonst problem+json (06 §4)."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response

from .context import current_request_id

env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"), autoescape=True)


def error(request: Request, status: int, title: str, detail: str) -> Response:
    request_id = current_request_id.get()
    if "text/html" in request.headers.get("accept", ""):
        html = env.get_template("error.html").render(title=title, detail=detail, request_id=request_id)
        return HTMLResponse(html, status_code=status)
    body = {"type": f"urn:hka:problem:{status}", "title": title, "status": status, "detail": detail}
    if request_id:
        body["request_id"] = request_id
    return JSONResponse(body, status_code=status, media_type="application/problem+json")
