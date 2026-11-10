"""Prober, Nachladen und Menü mit Status (HKA-53, AK1 und AK2)."""

import asyncio
import dataclasses
import os
import re
import time
from datetime import datetime, timezone

import httpx
import pytest
from conftest import login, write_manifest
from fastapi.testclient import TestClient

from portal.app import create_app
from portal.core.config import RegistryConfig, load_config
from portal.registry import Prober, prober as prober_module

ISSUER = "http://portal.test/"
NOW = datetime(2026, 11, 4, 9, 0, 0, tzinfo=timezone.utc)


def manifest(slug="pruefung", **changes):
    return {"slug": slug, "name": "Prüfungen", "category": "Studium", "menu": {"label": "Prüfungen", "icon": "grades"},
            "roles": ["student"], "version": "1.0.0", **changes}


class FakeApps:
    """Ersatz für die App-Container: protokolliert Anfragen, ``down`` und ``status`` steuern die Antwort."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.down: set[str] = set()
        self.status = 200

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.host.removeprefix("app-") in self.down:
            raise httpx.ConnectError("Verbindung abgelehnt", request=request)
        return httpx.Response(self.status, content=b"ok")


class Clock:
    """Feste Uhr, die der Test vorstellt."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def apps() -> FakeApps:
    return FakeApps()


@pytest.fixture
def probe_cfg(env):
    """Konfiguration mit ``registry.probe``, ohne Statusdatei und ohne die Beispiel-Manifeste."""
    path = env / "gateway.dev.yml"
    text = path.read_text(encoding="utf-8").replace("state_file: state.yml\n", "")
    path.write_text(
        text + "\napps:\n  upstream: http://app-{slug}:8080\nregistry:\n  probe: true\n",
        encoding="utf-8",
    )
    for f in (env / "manifests").glob("*.json"):
        f.unlink()
    return path


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def gw(probe_cfg, apps) -> TestClient:
    return TestClient(create_app(probe_cfg, app_transport=httpx.MockTransport(apps)), follow_redirects=False)


@pytest.fixture
def prober(gw, apps, clock) -> Prober:
    """Prober mit fester Uhr auf der Registry des Portals; der eingebaute Prober läuft im Test nicht."""
    portal = gw.app.state.portal
    return Prober(portal.registry, portal.cfg.apps, httpx.MockTransport(apps), monotonic=clock, wall=lambda: NOW)


def drive(prober: Prober, clock: Clock, seconds: int) -> None:
    """Die Uhr Sekunde für Sekunde vorstellen und jedes Mal prüfen, was fällig ist."""
    async def go() -> None:
        for _ in range(seconds):
            clock.now += 1
            await prober.tick()
    asyncio.run(go())


def add(gw, env, **changes) -> None:
    write_manifest(env, manifest(**changes))
    gw.app.state.portal.registry.refresh()


def status_of(gw, slug="pruefung") -> str:
    return gw.app.state.portal.registry.snapshot().apps[slug].status


def test_new_app_starts_registering_and_is_not_in_menu(gw, env):
    add(gw, env)
    assert status_of(gw) == "registering"
    assert "Prüfungen" not in login(gw, "alexandru").get("/").text
    assert gw.get("/apps/pruefung/").status_code == 404            # nicht geroutet, auch ohne Anmeldung


def test_app_becomes_healthy_after_three_ok_in_a_row(gw, env, prober, clock):
    add(gw, env)
    drive(prober, clock, 4)
    assert status_of(gw) == "registering"          # Prüfungen nach 1 s, 3 s: erst 2 Erfolge
    drive(prober, clock, 1)
    assert status_of(gw) == "healthy"              # 3. Erfolg nach 5 s
    app = gw.app.state.portal.registry.snapshot().apps["pruefung"]
    assert app.last_probe_at == "2026-11-04 09:00:00 UTC"


def test_ak1_registered_app_appears_in_menu_for_its_roles_within_60_seconds(gw, env, prober, clock):
    add(gw, env)
    drive(prober, clock, 10)
    html = login(gw, "alexandru").get("/").text
    assert "Prüfungen" in html and "nicht verfügbar" not in html
    gw.cookies.clear()
    assert "Prüfungen" not in login(gw, "max").get("/").text       # employee hat die Rolle nicht
    gw.cookies.clear()
    assert "Prüfungen" not in login(gw, "gast").get("/").text


def test_app_that_never_answers_fails_after_60_seconds(gw, env, prober, clock, apps):
    apps.down.add("pruefung")
    add(gw, env)
    drive(prober, clock, 59)
    assert status_of(gw) == "registering"
    drive(prober, clock, 5)
    assert status_of(gw) == "failed"
    assert "Prüfungen" not in login(gw, "alexandru").get("/").text
    assert login(gw, "alexandru").get("/apps/pruefung/").status_code == 404


def test_a_failure_in_between_restarts_the_count(gw, env, prober, clock, apps):
    add(gw, env)
    drive(prober, clock, 2)                          # Prüfung bei 1 s: ok=1
    apps.down.add("pruefung")
    drive(prober, clock, 2)                          # Prüfung bei 3 s: Fehler, Zählung beginnt neu
    apps.down.clear()
    drive(prober, clock, 4)                          # Prüfungen bei 5 s und 7 s: erst 2 Erfolge
    assert status_of(gw) == "registering"
    drive(prober, clock, 2)                          # Prüfung bei 9 s: der dritte
    assert status_of(gw) == "healthy"


def healthy(gw, env, prober, clock) -> None:
    add(gw, env)
    drive(prober, clock, 5)
    assert status_of(gw) == "healthy"


def test_ak2_stopped_container_becomes_unhealthy_and_menu_says_not_available(gw, env, prober, clock, apps):
    healthy(gw, env, prober, clock)
    apps.down.add("pruefung")
    drive(prober, clock, 30)                         # Prüfung bei 35 s nach dem Start: erster Fehler
    assert status_of(gw) == "healthy"
    drive(prober, clock, 30)                         # nach 10 s und 10 s: dritter Fehler
    assert status_of(gw) == "unhealthy"
    client = login(gw, "alexandru")
    html = client.get("/").text
    assert re.search(r'Prüfungen\s*<span class="badge badge--unhealthy small">nicht verfügbar</span>', html)
    assert client.get("/apps/pruefung/").status_code == 503
    nav = client.get("/nav").text
    assert "nicht verfügbar" in nav


def test_ak2_unhealthy_app_is_healthy_again_after_one_ok(gw, env, prober, clock, apps):
    healthy(gw, env, prober, clock)
    apps.down.add("pruefung")
    drive(prober, clock, 60)
    assert status_of(gw) == "unhealthy"
    apps.down.clear()
    drive(prober, clock, 10)
    assert status_of(gw) == "healthy"
    assert "nicht verfügbar" not in login(gw, "alexandru").get("/").text


def test_failed_app_comes_back_when_the_container_returns(gw, env, prober, clock, apps):
    apps.down.add("pruefung")
    add(gw, env)
    drive(prober, clock, 65)
    assert status_of(gw) == "failed"
    apps.down.clear()
    drive(prober, clock, 30)                         # nach höchstens 30 s: erster Erfolg, Status registering
    assert status_of(gw) in ("registering", "healthy")
    drive(prober, clock, 10)
    assert status_of(gw) == "healthy"


def test_probe_sends_no_token_no_cookie_and_follows_no_redirect(gw, env, prober, clock, apps):
    add(gw, env)
    drive(prober, clock, 1)
    request = apps.requests[-1]
    assert request.method == "GET" and request.url.path == "/healthz" and request.url.host == "app-pruefung"
    assert request.url.port == 8080
    assert "x-portal-assertion" not in request.headers and "cookie" not in request.headers
    assert "authorization" not in request.headers


def test_only_status_200_counts_as_ok(gw, env, prober, clock, apps):
    for status in (204, 301, 302, 401, 404, 500, 503):
        apps.status = status
        apps.requests.clear()
        add(gw, env, version=f"1.0.{status}")
        drive(prober, clock, 20)
        assert status_of(gw) == "registering", status
        assert len(apps.requests) >= 3                               # es wird nicht zu einer Weiterleitung gefolgt
        assert all(r.url.path == "/healthz" for r in apps.requests)


def test_new_registration_starts_over_at_registering(gw, env, prober, clock):
    healthy(gw, env, prober, clock)
    add(gw, env, version="1.1.0")
    assert status_of(gw) == "registering"
    drive(prober, clock, 5)
    assert status_of(gw) == "healthy"
    path = env / "manifests" / "pruefung.json"
    later = time.time() + 5
    os.utime(path, (later, later))                    # dieselbe Datei, neu bereitgestellt
    gw.app.state.portal.registry.refresh()
    assert status_of(gw) == "registering"


def test_other_apps_keep_their_status_when_a_manifest_is_added(gw, env, prober, clock):
    healthy(gw, env, prober, clock)
    add(gw, env, slug="zweite", name="Zweite", menu={"label": "Zweite", "icon": "info"})
    snapshot = gw.app.state.portal.registry.snapshot()
    assert snapshot.apps["pruefung"].status == "healthy"
    assert snapshot.apps["zweite"].status == "registering"


def test_removed_manifest_removes_the_app(gw, env, prober, clock):
    healthy(gw, env, prober, clock)
    (env / "manifests" / "pruefung.json").unlink()
    gw.app.state.portal.registry.refresh()
    assert "pruefung" not in gw.app.state.portal.registry.snapshot().apps
    drive(prober, clock, 3)                           # kein Fehler, kein Eintrag mehr
    assert "pruefung" not in gw.app.state.portal.registry.snapshot().apps


def test_set_status_ignores_a_stale_registration(gw, env):
    add(gw, env)
    registry = gw.app.state.portal.registry
    old = registry.snapshot().apps["pruefung"]
    add(gw, env, version="2.0.0")
    assert registry.set_status(old, "healthy", "x") is False
    assert registry.snapshot().apps["pruefung"].status == "registering"


def test_at_most_four_probes_at_the_same_time(gw, env, prober, clock):
    for i in range(10):
        write_manifest(env, manifest(slug=f"app-nr-{i}", name=f"App {i}", menu={"label": f"App {i}", "icon": "info"}))
    gw.app.state.portal.registry.refresh()
    running = peak = 0

    async def slow(request: httpx.Request) -> httpx.Response:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.01)
        running -= 1
        return httpx.Response(200)

    slow_prober = Prober(gw.app.state.portal.registry, gw.app.state.portal.cfg.apps, httpx.MockTransport(slow),
                         monotonic=clock, wall=lambda: NOW)
    drive(slow_prober, clock, 1)
    assert peak == 4


def test_registry_without_probe_keeps_status_from_the_state_file(client):
    portal = client.app.state.portal
    assert portal.prober is None
    assert portal.registry.snapshot().apps["raumbuchung"].status == "unhealthy"
    portal.registry.reload()
    assert portal.registry.snapshot().apps["raumbuchung"].status == "unhealthy"


def test_watch_picks_up_a_new_manifest_without_restart(gw, env):
    registry = gw.app.state.portal.registry

    async def go() -> None:
        task = asyncio.create_task(registry.watch(0.02))
        await asyncio.sleep(0.05)
        write_manifest(env, manifest())
        await asyncio.sleep(0.15)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(go())
    assert "pruefung" in registry.snapshot().apps


def test_watch_survives_a_failing_source(gw, env, caplog):
    registry = gw.app.state.portal.registry
    calls = 0

    def broken() -> None:
        nonlocal calls
        calls += 1
        raise OSError("Ordner nicht lesbar")

    registry.refresh = broken

    async def go() -> None:
        task = asyncio.create_task(registry.watch(0.01))
        await asyncio.sleep(0.1)
        assert not task.done()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(go())
    assert calls >= 2 and "registry_refresh_failed" in caplog.text


def test_end_to_end_with_lifespan_manifest_to_menu(probe_cfg, env, apps, monkeypatch):
    """Alles zusammen mit echten Uhren: Datei ablegen, Portal lädt nach, Prober macht die App gesund, Menü zeigt sie."""
    monkeypatch.setattr(prober_module, "TICK_SECONDS", 0.02)
    monkeypatch.setitem(prober_module.INTERVAL_SECONDS, "registering", 0.02)
    cfg = dataclasses.replace(load_config(probe_cfg), registry=RegistryConfig(refresh_seconds=0.05, probe=True))
    app = create_app(cfg, app_transport=httpx.MockTransport(apps))
    started = time.monotonic()
    with TestClient(app, follow_redirects=False) as client:
        login(client, "alexandru")
        assert "Prüfungen" not in client.get("/").text
        write_manifest(env, manifest())
        deadline = started + 20
        while time.monotonic() < deadline and "Prüfungen" not in client.get("/").text:
            time.sleep(0.05)
        assert "Prüfungen" in client.get("/").text
        assert client.get("/apps/pruefung/").status_code == 200
    assert time.monotonic() - started < 20


def test_portal_builds_a_prober_with_probe(gw):
    assert isinstance(gw.app.state.portal.prober, Prober)


def test_hka56_prober_writes_the_status_file_after_each_round(gw, env, apps, clock):
    """Der Prober schreibt den Status in die Statusdatei, die ``list`` liest (HKA-56, AK1)."""
    from portal.registry import StatusWriter, read_status

    path = env / "status.json"
    portal = gw.app.state.portal
    prober = Prober(portal.registry, portal.cfg.apps, httpx.MockTransport(apps), monotonic=clock, wall=lambda: NOW,
                    status_writer=StatusWriter(path, monotonic=clock, wall=lambda: NOW))
    add(gw, env)
    drive(prober, clock, 1)
    assert read_status(path).apps["pruefung"]["status"] == "registering"
    drive(prober, clock, 4)
    report = read_status(path)
    assert report.apps["pruefung"] == {"status": "healthy", "version": "1.0.0", "last_probe_at": "2026-11-04 09:00:00 UTC"}
    assert report.written_at == NOW


def test_hka56_portal_wires_the_status_file_from_the_config(probe_cfg, apps):
    path = probe_cfg.read_text(encoding="utf-8").replace("registry:\n  probe: true\n",
                                                          "registry:\n  probe: true\n  status_file: status.json\n")
    probe_cfg.write_text(path, encoding="utf-8")
    portal = create_app(probe_cfg, app_transport=httpx.MockTransport(apps)).state.portal
    assert portal.prober._status_writer is not None
    assert portal.cfg.registry.status_file == (probe_cfg.parent / "status.json").resolve()
