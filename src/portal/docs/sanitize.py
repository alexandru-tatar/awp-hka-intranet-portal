"""HTML aus dem Docs-Editor bereinigen, bevor es gespeichert wird.

Erlaubt ist nur, was die Dokumentation selbst verwendet: Text, Überschriften, Listen, Tabellen, Hinweisboxen,
Code-Blöcke, Bilder aus dem Docs-Speicher und die Icons des Sprites. Alles andere entfällt: Skripte, Event-Handler
(``on…``), ``javascript:``-Links, eingebettete Fremdinhalte, Formulare. Unbekannte Tags fallen weg, ihr Text bleibt.
"""

from __future__ import annotations

import re
from html import escape
from html.parser import HTMLParser
from typing import Final

#: Tags, die mit ihrem ganzen Inhalt entfallen.
DROP_WITH_CONTENT: Final = frozenset({
    "script", "style", "iframe", "object", "embed", "applet", "frame", "frameset", "noscript", "template",
    "textarea", "select", "option", "math", "foreignobject", "animate", "animatemotion", "animatetransform",
    "set", "head", "title_outside_svg",
})

#: Leere Elemente ohne End-Tag.
VOID: Final = frozenset({"br", "hr", "img", "input", "wbr", "col"})

_HTML_TAGS: Final = frozenset({
    "a", "abbr", "article", "aside", "b", "blockquote", "br", "button", "caption", "cite", "code", "col",
    "colgroup", "dd", "del", "details", "div", "dl", "dt", "em", "figcaption", "figure", "h1", "h2", "h3", "h4",
    "h5", "h6", "header", "hr", "i", "img", "input", "ins", "kbd", "label", "li", "mark", "nav", "ol", "p", "pre",
    "q", "s", "samp", "section", "small", "span", "strong", "sub", "summary", "sup", "table", "tbody", "td",
    "tfoot", "th", "thead", "time", "tr", "u", "ul", "var", "wbr",
})
_SVG_TAGS: Final = frozenset({
    "svg", "use", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "g", "defs", "marker",
    "text", "tspan", "title", "desc",
})
ALLOWED_TAGS: Final = _HTML_TAGS | _SVG_TAGS

_GLOBAL_ATTRS: Final = frozenset({"class", "id", "title", "role", "lang", "dir", "style", "hidden", "tabindex"})
_TAG_ATTRS: Final = {
    "a": {"href", "target", "rel", "download"},
    "img": {"src", "alt", "width", "height", "loading", "decoding"},
    "input": {"type", "checked", "disabled", "autocomplete", "placeholder"},
    "label": {"for"},
    "button": {"type"},
    "td": {"colspan", "rowspan", "scope"},
    "th": {"colspan", "rowspan", "scope"},
    "col": {"span"},
    "ol": {"start", "reversed"},
    "time": {"datetime"},
    "details": {"open"},
    "q": {"cite"},
    "blockquote": {"cite"},
}
_SVG_ATTRS: Final = frozenset({
    "viewbox", "width", "height", "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry", "d", "points",
    "transform", "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "stroke-dasharray",
    "fill-rule", "opacity", "marker-start", "marker-end", "marker-mid", "orient", "refx", "refy",
    "markerwidth", "markerheight", "markerunits", "text-anchor", "dominant-baseline", "font-size", "font-weight",
    "xmlns", "focusable", "preserveaspectratio", "href", "xlink:href",
})

_INPUT_TYPES: Final = frozenset({"checkbox", "search", "text"})
_SAFE_SCHEMES: Final = ("http:", "https:", "mailto:", "tel:")
_STYLE_BLOCKLIST: Final = re.compile(r"url\s*\(|expression\s*\(|javascript:|@import|behavior\s*:|-moz-binding", re.I)
_CONTROL: Final = re.compile(r"[\x00-\x20\x7f]+")
_DATA_OR_ARIA: Final = re.compile(r"^(data|aria)-[a-z0-9_.:-]+$")


def sanitize_html(html: str, *, asset_prefix: str) -> str:
    """HTML aus dem Editor auf die erlaubten Tags und Attribute reduzieren.

    :param html: HTML aus dem Editor (Inhalt einer Seite ohne ``<article>``)
    :param asset_prefix: Pfad, unter dem hochgeladene Dateien liegen, z. B. ``/_portal/docs/assets/``;
        Bilder dürfen nur von dort kommen
    :return: Bereinigtes HTML
    :rtype: str
    """
    cleaner = _Cleaner(asset_prefix)
    cleaner.feed(html)
    cleaner.close()
    return cleaner.result()


def _url_ok(value: str, *, image: bool, asset_prefix: str) -> bool:
    """Ob eine URL in ``href`` bzw. ``src`` erlaubt ist.

    :param value: URL aus dem Attribut
    :param image: ``True`` für ``img src``: nur Dateien aus dem Docs-Speicher
    :param asset_prefix: Pfad der hochgeladenen Dateien
    :return: ``True``, falls erlaubt
    :rtype: bool
    """
    v = _CONTROL.sub("", value).lower()
    if image:
        return v.startswith(asset_prefix.lower())
    if v.startswith(("#", "/", "./", "../", "?")):
        return not v.startswith("//")
    if ":" not in v.split("/", 1)[0]:
        return True  # relativer Pfad ohne Schema
    return v.startswith(_SAFE_SCHEMES)


class _Cleaner(HTMLParser):
    """Baut das HTML Tag für Tag neu auf und lässt dabei nur Erlaubtes durch."""

    def __init__(self, asset_prefix: str) -> None:
        """:param asset_prefix: Pfad der hochgeladenen Dateien"""
        super().__init__(convert_charrefs=False)
        self._out: list[str] = []
        self._open: list[str] = []
        self._skip: list[str] = []
        self._svg_depth = 0
        self._asset_prefix = asset_prefix

    def result(self) -> str:
        """Ergebnis mit geschlossenen offenen Tags.

        :return: Bereinigtes HTML
        :rtype: str
        """
        while self._open:
            self._out.append(f"</{self._open.pop()}>")
        return "".join(self._out)

    def _attrs(self, tag: str, attrs: list[tuple[str, str | None]]) -> str:
        """Erlaubte Attribute eines Tags als Text.

        :param tag: Tag-Name in Kleinbuchstaben
        :param attrs: Attribute aus dem Parser
        :return: Attribute mit führendem Leerzeichen, leer ohne Attribute
        :rtype: str
        """
        svg = tag in _SVG_TAGS
        allowed = _GLOBAL_ATTRS | _TAG_ATTRS.get(tag, set()) | (_SVG_ATTRS if svg else set())
        parts: list[str] = []
        names: set[str] = set()
        target_blank = False
        for name, value in attrs:
            name = name.lower()
            if name in names or not (name in allowed or _DATA_OR_ARIA.match(name)):
                continue
            value = value if value is not None else ""
            if name in ("href", "xlink:href"):
                if svg:
                    if not value.startswith("#"):
                        continue
                elif not _url_ok(value, image=False, asset_prefix=self._asset_prefix):
                    continue
            elif name == "src" and not _url_ok(value, image=True, asset_prefix=self._asset_prefix):
                continue
            elif name == "style" and (not value.strip() or _STYLE_BLOCKLIST.search(value)):
                continue
            elif name == "type" and tag == "input" and value.lower() not in _INPUT_TYPES:
                continue
            elif name == "type" and tag == "button" and value.lower() != "button":
                value = "button"
            elif name == "target":
                if value not in ("_blank", "_self"):
                    continue
                target_blank = value == "_blank"
            elif name == "rel":
                continue  # wird unten passend gesetzt
            names.add(name)
            parts.append(f' {name}="{escape(value, quote=True).replace(chr(10), "&#10;")}"')
        if tag == "a" and target_blank:
            parts.append(' rel="noopener noreferrer"')
        if tag == "img" and "src" not in names:
            return "\0"  # Bild ohne erlaubte Quelle entfällt
        return "".join(parts)

    def _start(self, tag: str, attrs: list[tuple[str, str | None]], *, closed: bool) -> None:
        """Gemeinsamer Teil für Start-Tags mit und ohne ``/>``.

        :param tag: Tag-Name
        :param attrs: Attribute
        :param closed: ``True`` bei ``<tag/>``
        """
        tag = tag.lower()
        if self._skip:
            if not closed and tag not in VOID:
                self._skip.append(tag)
            return
        if tag == "title" and self._svg_depth == 0:
            tag = "title_outside_svg"
        if tag in DROP_WITH_CONTENT:
            if not closed and tag not in VOID:
                self._skip.append(tag)
            return
        if tag not in ALLOWED_TAGS or (tag in _SVG_TAGS and tag != "svg" and self._svg_depth == 0):
            return
        rendered = self._attrs(tag, attrs)
        if rendered == "\0":
            return
        if tag in VOID:
            self._out.append(f"<{tag}{rendered}>")
            return
        if closed and tag in _SVG_TAGS:
            self._out.append(f"<{tag}{rendered}/>")
            return
        self._out.append(f"<{tag}{rendered}>")
        self._open.append(tag)
        if tag == "svg":
            self._svg_depth += 1

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Start-Tag übernehmen, falls erlaubt.

        :param tag: Tag-Name
        :param attrs: Attribute
        """
        self._start(tag, attrs, closed=False)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Selbstschließendes Tag übernehmen, falls erlaubt.

        :param tag: Tag-Name
        :param attrs: Attribute
        """
        self._start(tag, attrs, closed=True)

    def handle_endtag(self, tag: str) -> None:
        """End-Tag übernehmen, falls das Tag offen ist; schließt dazwischen offene Tags mit.

        :param tag: Tag-Name
        """
        tag = tag.lower()
        if self._skip:
            if tag == self._skip[-1] or (tag == "title" and self._skip[-1] == "title_outside_svg"):
                self._skip.pop()
            return
        if tag in VOID or tag not in self._open:
            return
        while self._open:
            top = self._open.pop()
            self._out.append(f"</{top}>")
            if top == "svg":
                self._svg_depth -= 1
            if top == tag:
                break

    def handle_data(self, data: str) -> None:
        """Text übernehmen; ``<`` und ``>`` werden maskiert.

        :param data: Text
        """
        if not self._skip:
            self._out.append(data.replace("<", "&lt;").replace(">", "&gt;"))

    def handle_entityref(self, name: str) -> None:
        """Benannte Entität unverändert übernehmen.

        :param name: Name der Entität
        """
        if not self._skip:
            self._out.append(f"&{name};" if name.isalnum() else f"&amp;{name}")

    def handle_charref(self, name: str) -> None:
        """Numerische Entität unverändert übernehmen.

        :param name: Nummer, dezimal oder ``x…``
        """
        if not self._skip and re.fullmatch(r"x[0-9a-fA-F]{1,6}|[0-9]{1,7}", name):
            self._out.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        """Kommentare entfallen.

        :param data: Kommentar
        """

    def handle_decl(self, decl: str) -> None:
        """Deklarationen entfallen.

        :param decl: Deklaration
        """

    def unknown_decl(self, data: str) -> None:
        """CDATA und Ähnliches entfällt.

        :param data: Inhalt
        """

    def handle_pi(self, data: str) -> None:
        """Processing Instructions entfallen.

        :param data: Inhalt
        """
