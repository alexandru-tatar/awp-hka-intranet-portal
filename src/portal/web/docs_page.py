"""Docs-Seite zusammensetzen: Hülle aus ``portal/docs/shell.html``, Seiten aus dem Speicher, Seite „Letzte Änderungen“.

Die Hülle ist eine eigenständige HTML-Seite mit eigenem Stil und Skript. Das Skript bekommt eine Nonce; die
Content-Security-Policy lässt nur Skripte mit dieser Nonce zu, damit gespeicherter Inhalt nie Skript ausführt.
"""

from __future__ import annotations

import json
import secrets
from html import escape
from pathlib import Path
from typing import Final, Sequence

from ..service import DocChangeDTO, DocPageDTO, SessionDTO

DOCS_DIR: Final = Path(__file__).resolve().parent.parent / "docs"
CHANGES_SLUG: Final = "aenderungen"
CHANGES_GROUP: Final = "Hilfe"

_ACTIONS: Final = {
    "create": "hat {page} angelegt",
    "update": "hat {page} aktualisiert",
    "restore": "hat eine frühere Version von {page} wiederhergestellt",
    "delete": "hat {page} gelöscht",
}


def docs_csp(nonce: str) -> str:
    """Content-Security-Policy der Docs-Seite.

    :param nonce: Nonce des Skripts dieser Antwort
    :return: Wert des Headers
    :rtype: str
    """
    return (
        f"default-src 'self'; script-src 'nonce-{nonce}'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; object-src 'none'; "
        "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
    )


class DocsPage:
    """Rendert die Docs-Seite; liest Hülle und Editor einmal beim Start."""

    def __init__(self, directory: Path = DOCS_DIR) -> None:
        """:param directory: Ordner mit ``shell.html``, ``editor.js`` und ``editor.css``"""
        self._shell = (directory / "shell.html").read_text(encoding="utf-8")
        self._editor_js = (directory / "editor.js").read_text(encoding="utf-8")
        self._editor_css = (directory / "editor.css").read_text(encoding="utf-8")

    def render(self, *, pages: Sequence[DocPageDTO], changes: Sequence[DocChangeDTO], session: SessionDTO,
               can_edit: bool, writable: bool, max_upload_bytes: int) -> tuple[str, str]:
        """Ganze Seite als HTML.

        :param pages: Seiten in der Reihenfolge der Navigation
        :param changes: Letzte Änderungen, die neueste zuerst
        :param session: Angemeldete Session
        :param can_edit: Ob die Person bearbeiten darf
        :param writable: Ob der Speicher Änderungen zulässt
        :param max_upload_bytes: Größte erlaubte Datei beim Hochladen
        :return: HTML und die Nonce des Skripts
        :rtype: tuple[str, str]
        """
        nonce = secrets.token_urlsafe(18)
        articles = "\n".join(_article(p) for p in pages) + "\n" + _changes_article(changes)
        groups = list(dict.fromkeys(p.group for p in pages))
        boot = {
            "csrf": session.csrf,
            "user": session.name,
            "canEdit": bool(can_edit and writable),
            "readOnlyStore": not writable,
            "maxUpload": max_upload_bytes,
            "groups": groups,
            "api": "/_portal/docs/api",
            "last": _last_change(changes),
        }
        boot_json = json.dumps(boot, ensure_ascii=False).replace("<", "\\u003c")
        extra = (
            f'<style>{self._editor_css}</style>\n'
            f'<script type="application/json" id="docsBoot">{boot_json}</script>'
        )
        html = self._shell.replace("<!--DOCS:PAGES-->", articles, 1)
        html = html.replace("<!--DOCS:BOOT-->", extra, 1)
        html = html.replace("</body>", f'<script nonce="{nonce}">{self._editor_js}</script>\n</body>', 1)
        return html.replace("__NONCE__", nonce), nonce


def _attr(value: object) -> str:
    """Wert für ein HTML-Attribut maskieren.

    :param value: Wert
    :return: Maskierter Text
    :rtype: str
    """
    return escape(str(value), quote=True)


def _article(page: DocPageDTO) -> str:
    """Eine Seite als ``<article>`` mit den Angaben für Navigation und Zeile „Zuletzt aktualisiert“.

    :param page: Seite
    :return: HTML
    :rtype: str
    """
    attrs = "".join(f' data-{k}="{_attr(v)}"' for k, v in page.attrs)
    return (
        f'<article class="page" data-page="{_attr(page.slug)}" data-title="{_attr(page.title)}" '
        f'data-group="{_attr(page.group)}"{attrs} data-version="{page.version}" '
        f'data-created-at="{_attr(page.created_at)}" data-created-by="{_attr(page.created_by)}" '
        f'data-updated-at="{_attr(page.updated_at)}" data-updated-by="{_attr(page.updated_by)}">\n'
        f"{page.html}\n</article>"
    )


def _initials(name: str) -> str:
    """Initialen für das Namenskürzel.

    :param name: Name
    :return: Ein oder zwei Großbuchstaben
    :rtype: str
    """
    parts = [p for p in name.replace("-", " ").split() if p[:1].isalpha() and not p.endswith(".")]
    if not parts:
        return (name[:1] or "?").upper()
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()


def _changes_article(changes: Sequence[DocChangeDTO]) -> str:
    """Systemseite „Letzte Änderungen“ (nicht bearbeitbar).

    :param changes: Änderungen, die neueste zuerst
    :return: HTML
    :rtype: str
    """
    items: list[str] = []
    for c in changes:
        title = _attr(c.title)
        page = f'<a href="#{_attr(c.slug)}">{title}</a>' if c.exists and c.action != "delete" else f"<b>{title}</b>"
        what = _ACTIONS.get(c.action, _ACTIONS["update"]).format(page=page)
        note = f'<p class="chg-note">{_attr(c.note)}</p>' if c.note else ""
        version = f' · Version {c.version}' if c.version else ""
        history = (f' · <button type="button" class="chg-hist" data-docs-history="{_attr(c.slug)}">Verlauf</button>'
                   if c.exists else "")
        query = _attr(f"{c.title} {c.actor} {c.note}".lower())
        items.append(
            f'<li class="chg-it chg-{_attr(c.action)}" data-ts="{_attr(c.ts)}" data-q="{query}">'
            f'<span class="av" aria-hidden="true">{_attr(_initials(c.actor))}</span>'
            f'<div><p class="chg-what"><b>{_attr(c.actor)}</b> {what}</p>{note}'
            f'<small><time datetime="{_attr(c.ts)}">{_attr(c.ts[:16].replace("T", " "))} UTC</time>{version}{history}'
            f"</small></div></li>"
        )
    body = "\n".join(items) or '<li class="chg-empty">Noch keine Änderungen.</li>'
    return (
        f'<article class="page" data-page="{CHANGES_SLUG}" data-title="Letzte Änderungen" '
        f'data-group="{CHANGES_GROUP}" data-system="1">\n'
        "  <h1>Letzte Änderungen</h1>\n"
        '  <p class="lede">Wer hat wann welche Seite geändert – die neueste Änderung zuerst.</p>\n'
        '  <div class="chg-tools"><label class="sr" for="chgq">Änderungen filtern</label>'
        '<svg class="i" aria-hidden="true"><use href="#i-search"/></svg>'
        '<input id="chgq" type="search" placeholder="Nach Seite, Person oder Notiz filtern …" autocomplete="off">'
        '<span class="chg-count" id="chgCount" aria-live="polite"></span></div>\n'
        f'  <ol class="chg" id="chg">\n{body}\n  </ol>\n'
        '  <p class="chg-none" id="chgNone" hidden>Keine Änderung passt zum Filter.</p>\n'
        "</article>"
    )


def _last_change(changes: Sequence[DocChangeDTO]) -> dict | None:
    """Letzte Änderung für die Fußzeile der Docs.

    :param changes: Änderungen, die neueste zuerst
    :return: ``{"ts", "actor", "title", "slug"}`` oder ``None``
    :rtype: dict | None
    """
    if not changes:
        return None
    c = changes[0]
    return {"ts": c.ts, "actor": c.actor, "title": c.title, "slug": c.slug}
