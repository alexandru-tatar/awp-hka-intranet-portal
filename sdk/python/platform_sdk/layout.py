"""Seitenrahmen des Portals (04 §8, 06 §7).

Betrieb: Menü von `GET {PORTAL_API_URL}/nav`, Kit-Name aus dem Header `X-Portal-Kit`.
Entwicklung oder Menü nicht erreichbar: Menü aus dem eigenen Manifest.
Eigenes CSS der App wird immer als `{base_path}/static/app.css` eingebunden.
"""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

from .config import Config
from .context import User, current_assertion

log = logging.getLogger("platform_sdk")
env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"), autoescape=True)


class Layout:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._kit = "kit"  # zuletzt bekannter Kit-Name, damit der Ersatz-Rahmen gestaltet bleibt

    async def render(self, *, title: str, body: str, current: str, user: User) -> str:
        cfg = self.config
        nav_html = None
        if cfg.dev:
            kit = {"css": "/__dev/kit/kit.css", "js": "/__dev/kit/kit.js", "icons": "/__dev/kit/icons.svg"}
        else:
            nav_html = await self._fetch_nav()
            kit = {
                "css": f"/_portal/static/{self._kit}.css",
                "js": f"/_portal/static/{self._kit}.js",
                "icons": "/_portal/static/icons.svg",
            }
        if nav_html is None:
            nav_html = env.get_template("nav.html").render(item=self._menu_item(), current=current, kit=kit)
        return env.get_template("layout.html").render(
            title=title,
            body=Markup(body),  # Inhalt kommt aus einer Vorlage mit autoescape
            nav_html=Markup(nav_html),  # vom Portal oder aus nav.html
            user=user,
            kit=kit,
            app_css=f"{cfg.base_path}/static/app.css",
            dev=cfg.dev,
        )

    def _menu_item(self) -> dict:
        m = self.config.manifest
        return {
            "category": m["category"],
            "label": m["menu"]["label"],
            "icon": m["menu"]["icon"],
            "path": self.config.base_path or "/",
        }

    async def _fetch_nav(self) -> str | None:
        token = current_assertion.get()
        if token is None:
            return None
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                response = await client.get(f"{self.config.api_url}/nav", headers={"X-Portal-Assertion": token})
                response.raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("Menü nicht abrufbar, Ersatz-Menü: %s", type(exc).__name__)
            return None
        self._kit = response.headers.get("x-portal-kit", self._kit)
        return response.text
