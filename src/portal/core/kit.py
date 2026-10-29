"""Asset-URLs des Design-Kits aus ``kit-manifest.json`` (04 §11)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

STATIC_PREFIX = "/_portal/static"


def is_static_path(path: str) -> bool:
    """Ob der Pfad zu den Static-Dateien des Kits gehört.

    :param path: Pfad der Anfrage
    :return: ``True`` bei Pfaden unter ``/_portal/static/``
    :rtype: bool
    """
    return path.startswith(STATIC_PREFIX + "/")


@dataclass(frozen=True)
class Kit:
    """Dateien eines Kit-Builds.

    :ivar version: Version des Kits
    :ivar css: Dateiname des gebauten CSS (mit Hash)
    :ivar js: Dateiname des gebauten JavaScript (mit Hash)
    :ivar icons: Dateiname des Icon-Sprites (mit Hash)
    """
    version: str
    css: str
    js: str
    icons: str

    @classmethod
    def load(cls, dist: Path) -> "Kit":
        """Das Kit aus dem Build-Ordner laden.

        :param dist: Ordner ``kit/dist``
        :return: Das Kit
        :rtype: Kit
        :raises FileNotFoundError: Falls ``kit-manifest.json`` fehlt, dann ``make kit`` ausführen
        """
        path = dist / "kit-manifest.json"
        if not path.exists():
            raise FileNotFoundError(f"{path} missing — run `make kit` first")
        m = json.loads(path.read_text(encoding="utf-8"))
        return cls(version=m["version"], css=m["kit.css"], js=m["kit.js"], icons=m["icons.svg"])

    @property
    def id(self) -> str:
        """Wert des Headers ``X-Portal-Kit``: ``kit-<hash>`` (04 §8).

        :return: Kennung des Builds
        :rtype: str
        """
        return self.css.rsplit(".", 1)[0]

    @property
    def css_url(self) -> str:
        """URL des CSS.

        :return: Pfad unter ``/_portal/static``
        :rtype: str
        """
        return f"{STATIC_PREFIX}/{self.css}"

    @property
    def js_url(self) -> str:
        """URL des JavaScript.

        :return: Pfad unter ``/_portal/static``
        :rtype: str
        """
        return f"{STATIC_PREFIX}/{self.js}"

    @property
    def icons_url(self) -> str:
        """URL des Icon-Sprites.

        :return: Pfad unter ``/_portal/static``
        :rtype: str
        """
        return f"{STATIC_PREFIX}/{self.icons}"
