"""Seiten, Fehlerseiten und das Menü-Fragment aus Templates rendern."""

from __future__ import annotations

from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from ..core.config import Config
from ..core.i18n import Messages
from ..core.kit import Kit
from ..service import AppService, SessionDTO
from .menu import current_slug

# Statuses mit eigenem Text in messages.de.yml; alle anderen fallen auf 4xx bzw. 5xx zurück.
_ERRORS_WITH_TEXT = {
    400, 401, 403, 404, 405, 408, 409, 410, 413, 414, 415, 422, 429, 501, 502, 503, 504,
}


def error_message_key(status: int) -> str:
    """Schlüssel der Fehlertexte zu einem Status.

    :param status: HTTP-Status
    :return: der Status selbst, wenn es dafür einen eigenen Text gibt; sonst ``5xx`` ab 500 und ``4xx`` darunter
    :rtype: str
    """
    if status in _ERRORS_WITH_TEXT:
        return str(status)
    return "5xx" if status >= 500 else "4xx"


class Views:
    """Rendert Seiten im Rahmen des Portals."""
    def __init__(self, templates_dir: Path, *, apps: AppService, t: Messages, kit: Kit, cfg: Config):
        """Konstruktor mit Templates und globalen Werten.

        :param templates_dir: Ordner mit den Jinja2-Templates
        :param apps: Service für das Menü
        :param t: UI-Texte
        :param kit: Asset-URLs des Design-Kits
        :param cfg: Konfiguration
        """
        self._templates = Jinja2Templates(directory=str(templates_dir))
        self._templates.env.globals.update(t=t, kit=kit, cfg=cfg)
        self._apps = apps
        self._t = t

    def page(self, request: Request, template: str, *, title: str, session: SessionDTO | None,
             current: str | None = None, show_nav: bool = True, status_code: int = 200,
             **context) -> HTMLResponse:
        """Eine ganze Seite im Rahmen des Portals rendern; das Menü erscheint nur für angemeldete Benutzer.

        :param request: Anfrage
        :param template: Pfad des Templates, z. B. ``pages/home.html``
        :param title: Titel der Seite
        :param session: Angemeldete Session oder ``None``
        :param current: Pfad der aktuellen Seite, markiert den Menüeintrag
        :param show_nav: ``False`` blendet das Menü aus
        :param status_code: HTTP-Status der Antwort
        :param context: Weitere Werte für das Template
        :return: Die Seite
        :rtype: HTMLResponse
        """
        return self._templates.TemplateResponse(
            request,
            template,
            {
                "page_title": title,
                "user": session,
                "nav_html": self.nav_html(session, current) if (session and show_nav) else None,
                "request_id": request.state.request_id,
                **context,
            },
            status_code=status_code,
        )

    def error(self, request: Request, status: int, session: SessionDTO | None) -> HTMLResponse:
        """Fehlerseite mit verständlichem Text und Fehlernummer rendern.

        :param request: Anfrage
        :param status: HTTP-Status
        :param session: Angemeldete Session oder ``None``
        :return: Die Fehlerseite mit diesem Status
        :rtype: HTMLResponse
        """
        key = error_message_key(status)
        title = self._t(f"error.{key}.title")
        body = self._t(f"error.{key}.body", request_id=request.state.request_id)
        return self.page(request, "pages/error.html", title=title, session=session, status_code=status,
                         error_title=title, error_body=body, status=status)

    def nav_html(self, session: SessionDTO | None, current: str | None) -> Markup:
        """Menü-Fragment für die Rollen der Session rendern.

        :param session: Angemeldete Session oder ``None`` (leeres Menü)
        :param current: Pfad der aktuellen Seite, markiert den Menüeintrag
        :return: Das HTML-Fragment
        :rtype: Markup
        """
        groups = self._apps.find_nav_groups(session.roles if session else frozenset())
        html = self._templates.get_template("partials/nav.html").render(
            groups=groups, current_slug=current_slug(current)
        )
        return Markup(html)
