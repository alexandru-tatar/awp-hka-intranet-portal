"""Clients für die Schnittstellen (06 §8).

Vorläufig von Hand geschrieben. Später erzeugt `tools/gen_clients.py` diesen Ordner
aus den OpenAPI-Dateien der Plattform. Ein Ordner je System: bwsync/, noten/.
"""

from __future__ import annotations

from ..config import Config
from .bwsync import BwSyncClient
from .noten import NotenClient
from .transport import FixtureTransport, HttpTransport


class Adapters:
    def __init__(self, config: Config) -> None:
        transport = HttpTransport(config.adapters_url) if config.adapters_url else FixtureTransport()
        self.noten = NotenClient(transport)
        self.bwsync = BwSyncClient(transport)


__all__ = ["Adapters"]
