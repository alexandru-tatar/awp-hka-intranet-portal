"""Prober: prüft ``/healthz`` jeder App und setzt ihren Status (03 §7, HKA-53).

Zustände und Abstände wie in 03 §7: ``registering`` (alle 2 s) wird nach 3 Erfolgen in Folge ``healthy`` (alle 30 s),
nach 60 s ohne diese 3 Erfolge ``failed``. Aus ``healthy`` wird nach 3 Fehlern in Folge ``unhealthy`` (alle 10 s), ein
Erfolg macht es wieder ``healthy``. Abweichungen:

- Nach einem Fehler in ``healthy`` kommt die nächste Prüfung nach 10 s statt nach 30 s. So steht ``unhealthy`` nach
  etwa einer halben Minute da und nicht erst nach eineinhalb.
- ``failed`` wird alle 30 s weiter geprüft. Ein Erfolg setzt die App auf ``registering`` zurück. So kommt eine App
  nach einem Neustart der VM von selbst wieder, ohne dass sie jemand neu registriert.
- Kein Jitter. Höchstens 4 Prüfungen laufen gleichzeitig.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Final

import httpx
from loguru import logger

from ..core.config import AppsConfig
from .models import AppView, format_time
from .status_file import StatusWriter
from .store import Registry

PROBE_TIMEOUT_SECONDS: Final = 2.0
TICK_SECONDS = 1.0  # wie oft geprüft wird, was fällig ist; Tests verkürzen es
MAX_IN_FLIGHT: Final = 4
OK_NEEDED: Final = 3
FAILURES_NEEDED: Final = 3
REGISTERING_DEADLINE_SECONDS: Final = 60.0
INTERVAL_SECONDS: Final[dict[str, float]] = {"registering": 2.0, "healthy": 30.0, "unhealthy": 10.0, "failed": 30.0}
RETRY_AFTER_FAILURE_SECONDS: Final = 10.0
USER_AGENT: Final = "hka-portal-prober"


@dataclass
class _Track:
    """Verlauf der Prüfungen einer App.

    :ivar registration: Die App, zu deren Registrierung der Verlauf gehört; eine neue Registrierung beginnt neu
    :ivar state: Status, den der Prober zuletzt gesetzt hat
    :ivar since: Zeitpunkt, seit dem die App in diesem Status ist
    :ivar next_at: Zeitpunkt der nächsten Prüfung
    :ivar ok: Erfolge in Folge
    :ivar failures: Fehler in Folge
    """
    registration: AppView
    state: str
    since: float
    next_at: float
    ok: int = 0
    failures: int = 0


class Prober:
    """Prüft regelmäßig ``GET <upstream>/healthz`` jeder App im Snapshot."""

    def __init__(
        self,
        registry: Registry,
        apps: AppsConfig,
        transport: httpx.AsyncBaseTransport | None = None,
        *,
        status_writer: StatusWriter | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        wall: Callable[[], datetime] = datetime.now,
    ) -> None:
        """Konstruktor.

        :param registry: Registry, deren Status gesetzt wird
        :param apps: Weiterleitung an die App-Container, liefert die Adresse jeder App
        :param transport: Transport statt des Netzwerks, für Tests
        :param status_writer: Schreibt nach jeder Runde den Status in die Statusdatei (HKA-56), ``None`` ohne Datei
        :param monotonic: Uhr für die Abstände
        :param wall: Uhr für die Anzeige der letzten Prüfung
        """
        self._registry = registry
        self._apps = apps
        self._status_writer = status_writer
        self._monotonic = monotonic
        self._wall = wall
        self._tracks: dict[str, _Track] = {}
        self._client = httpx.AsyncClient(
            transport=transport,
            timeout=httpx.Timeout(PROBE_TIMEOUT_SECONDS),
            follow_redirects=False,
            headers={"User-Agent": USER_AGENT},
        )

    async def aclose(self) -> None:
        """Den HTTP-Client schließen."""
        await self._client.aclose()

    async def run(self) -> None:
        """Jede Sekunde prüfen, was fällig ist, bis die Aufgabe abgebrochen wird."""
        while True:
            try:
                await self.tick()
            except Exception:
                logger.exception("probe_tick_failed")
            await asyncio.sleep(TICK_SECONDS)

    async def tick(self) -> None:
        """Alle fälligen Apps prüfen, den Status setzen und ihn in die Statusdatei schreiben."""
        now = self._monotonic()
        snapshot = self._registry.snapshot()
        for slug in set(self._tracks) - set(snapshot.apps):
            del self._tracks[slug]
        due: list[tuple[AppView, _Track]] = []
        for app in snapshot.apps.values():
            track = self._tracks.get(app.slug)
            if track is None or track.state != app.status or not track.registration.same_registration(app):
                track = self._tracks[app.slug] = _Track(registration=app, state=app.status, since=now, next_at=now)
            if now >= track.next_at:
                due.append((app, track))
        gate = asyncio.Semaphore(MAX_IN_FLIGHT)

        async def probe_one(app: AppView, track: _Track) -> None:
            async with gate:
                ok = await self._probe(app)
            self._apply(app, track, ok, self._monotonic())

        await asyncio.gather(*(probe_one(app, track) for app, track in due))
        if self._status_writer is not None:
            self._status_writer.write(self._registry.snapshot())

    async def _probe(self, app: AppView) -> bool:
        """``GET /healthz`` an den Container der App, ohne Token und ohne Weiterleitung.

        Der Body wird nicht gelesen. Nur der Status 200 zählt.

        :param app: Die App
        :return: ``True`` bei Status 200
        :rtype: bool
        """
        url = f"{self._apps.upstream_for(app.slug)}/healthz"
        try:
            async with self._client.stream("GET", url) as response:
                ok = response.status_code == 200
                if not ok:
                    logger.debug("probe_failed slug={} status={}", app.slug, response.status_code)
                return ok
        except httpx.HTTPError as exc:
            logger.debug("probe_failed slug={} reason={}", app.slug, type(exc).__name__)
            return False

    def _apply(self, app: AppView, track: _Track, ok: bool, now: float) -> None:
        """Ergebnis einer Prüfung in den Verlauf und, bei einem Wechsel, in die Registry übernehmen.

        :param app: Die geprüfte Ansicht
        :param track: Verlauf der App
        :param ok: Ergebnis der Prüfung
        :param now: Zeitpunkt der Prüfung (monoton)
        """
        new_state = self._next_state(track, ok, now)
        probed_at = format_time(self._wall())
        if new_state != track.state:
            if not self._registry.set_status(app, new_state, probed_at):
                return  # Registrierung hat sich währenddessen geändert: der nächste Lauf beginnt neu
            logger.info("registry_change slug={} from={} to={}", app.slug, track.state, new_state)
            self._enter(track, new_state, now, ok)
        else:
            self._registry.set_status(app, track.state, probed_at)
        track.next_at = now + self._delay(track, ok)

    @staticmethod
    def _next_state(track: _Track, ok: bool, now: float) -> str:
        """Neuer Status nach einer Prüfung. Zählt die Erfolge und Fehler im Verlauf mit.

        :param track: Verlauf der App
        :param ok: Ergebnis der Prüfung
        :param now: Zeitpunkt der Prüfung (monoton)
        :return: Der neue Status, bei keinem Wechsel der bisherige
        :rtype: str
        """
        if ok:
            track.ok += 1
            track.failures = 0
        else:
            track.failures += 1
            track.ok = 0
        if track.state == "registering":
            if track.ok >= OK_NEEDED:
                return "healthy"
            if now - track.since >= REGISTERING_DEADLINE_SECONDS:
                return "failed"
        elif track.state == "healthy" and track.failures >= FAILURES_NEEDED:
            return "unhealthy"
        elif track.state == "unhealthy" and ok:
            return "healthy"
        elif track.state == "failed" and ok:
            return "registering"
        return track.state

    @staticmethod
    def _enter(track: _Track, state: str, now: float, ok: bool) -> None:
        """Verlauf für einen neuen Status zurücksetzen.

        :param track: Verlauf der App
        :param state: Neuer Status
        :param now: Zeitpunkt des Wechsels (monoton)
        :param ok: Ergebnis der Prüfung, die den Wechsel ausgelöst hat
        """
        track.state = state
        track.since = now
        track.failures = 0
        track.ok = 1 if (state == "registering" and ok) else 0

    @staticmethod
    def _delay(track: _Track, ok: bool) -> float:
        """Abstand bis zur nächsten Prüfung.

        :param track: Verlauf der App (mit dem Status nach dieser Prüfung)
        :param ok: Ergebnis der Prüfung
        :return: Sekunden
        :rtype: float
        """
        if track.state == "healthy" and not ok:
            return RETRY_AFTER_FAILURE_SECONDS
        return INTERVAL_SECONDS[track.state]
