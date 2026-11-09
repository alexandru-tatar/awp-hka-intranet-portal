"""Manifeste verwalten: ``list``, Aktualisieren und ``remove`` mit Sperrfrist (HKA-56, AK1 bis AK4)."""

import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from portal.core.config import load_config
from portal.registry import ManifestDirectorySource, ManifestValidator, Registry, StatusWriter, read_status
from portal.registry.__main__ import main
from portal.registry.models import AppView, Snapshot

OWNER = "alexandru-tatar/pruefungen"
OTHER = "jemand/anderes-repo"
GOOD = {"slug": "pruefung", "name": "Prüfungen", "category": "Studium",
        "menu": {"label": "Prüfungen", "icon": "grades"}, "roles": ["student"], "version": "1.0.0"}
T0 = datetime(2026, 11, 8, 15, 0, 0, tzinfo=timezone.utc)


class Clock:
    """Uhr mit Zeitzone, die der Test vorstellt."""

    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def cfg_path(env) -> Path:
    """Konfiguration mit Besitzer- und Statusdatei; der Manifest-Ordner ist leer."""
    path = env / "gateway.dev.yml"
    (env / "registry").mkdir()
    (env / "status").mkdir()
    for f in (env / "manifests").glob("*.json"):
        f.unlink()
    path.write_text(path.read_text(encoding="utf-8") + "\nregistry:\n  owners_file: registry/owners.json\n"
                    "  status_file: status/status.json\n", encoding="utf-8")
    return path


@pytest.fixture
def manifests(env) -> Path:
    return env / "manifests"


def run(cfg_path, clock, *args, manifest=None, owner=OWNER):
    """Den Befehl aufrufen. ``check``/``register`` bekommen das Manifest auf der Standardeingabe.

    :return: Exit-Code, Standardausgabe, Fehlerausgabe
    """
    command, rest = args[0], list(args[1:])
    argv = [command, *rest, "--config", str(cfg_path)]
    if command != "list":
        argv += ["--owner", owner]
    raw = json.dumps(manifest if manifest is not None else GOOD).encode()
    out, err = io.StringIO(), io.StringIO()
    code = main(argv, io.BytesIO(raw), out, err, now=clock)
    return code, out.getvalue(), err.getvalue()


def files(folder: Path) -> dict[str, bytes]:
    """Alle Dateien samt Inhalt, ohne Sperrdatei."""
    return {str(p.relative_to(folder)): p.read_bytes() for p in sorted(folder.rglob("*"))
            if p.is_file() and not p.name.endswith(".lock")}


def registry_for(cfg_path, manifests) -> Registry:
    """Registry des Portals über dem Manifest-Ordner, wie mit ``registry.probe``."""
    cfg = load_config(cfg_path)
    validator = ManifestValidator(cfg.schema_path, cfg.role_vocabulary, cfg.adapter_scopes)
    return Registry(ManifestDirectorySource(manifests, validator, probe=True), keep_status=True)


def write_status(env, apps: dict, written_at: datetime) -> None:
    """Statusdatei so schreiben, wie der Prober es täte."""
    snapshot = Snapshot(version=1, apps={
        slug: AppView.from_manifest({**GOOD, "slug": slug}, status=status, last_probe_at="2026-11-08 14:59:50 UTC")
        for slug, status in apps.items()})
    StatusWriter(env / "status" / "status.json", wall=lambda: written_at).write(snapshot)


# --- AK1: list ----------------------------------------------------------------------------------------------------


def test_ak1_list_shows_slug_owner_and_status(cfg_path, env, clock):
    assert run(cfg_path, clock, "register")[0] == 0
    assert run(cfg_path, clock, "register", manifest={**GOOD, "slug": "noten"}, owner=OTHER)[0] == 0
    write_status(env, {"pruefung": "healthy", "noten": "unhealthy"}, T0 - timedelta(seconds=10))
    code, out, err = run(cfg_path, clock, "list")
    assert (code, err) == (0, "")
    lines = out.splitlines()
    assert lines[0].split() == ["SLUG", "BESITZER", "VERSION", "STATUS", "LETZTE", "PRÜFUNG"]
    assert lines[1].split()[:4] == ["noten", OTHER, "1.0.0", "unhealthy"]
    assert lines[2].split()[:4] == ["pruefung", OWNER, "1.0.0", "healthy"]
    assert "Status vom 08.11.2026 14:59:50" in out


def test_ak1_list_without_portal_shows_unknown_and_a_hint(cfg_path, clock):
    run(cfg_path, clock, "register")
    code, out, _ = run(cfg_path, clock, "list")
    assert code == 0 and "unbekannt" in out and "Keine Statusdatei gefunden" in out


def test_ak1_list_with_an_old_status_file_does_not_show_old_status(cfg_path, env, clock):
    run(cfg_path, clock, "register")
    write_status(env, {"pruefung": "healthy"}, T0 - timedelta(minutes=5))
    code, out, _ = run(cfg_path, clock, "list")
    assert code == 0 and "healthy" not in out and "unbekannt" in out and "Läuft das Portal?" in out


def test_ak1_app_not_yet_taken_over_by_the_portal(cfg_path, env, clock):
    write_status(env, {}, T0)
    run(cfg_path, clock, "register")
    assert "noch nicht übernommen" in run(cfg_path, clock, "list")[1]


def test_list_shows_retired_and_hand_made_apps(cfg_path, manifests, clock):
    run(cfg_path, clock, "register")
    run(cfg_path, clock, "remove", "pruefung")
    (manifests / "handarbeit.json").write_text(json.dumps({**GOOD, "slug": "handarbeit"}), encoding="utf-8")
    out = run(cfg_path, clock, "list")[1]
    assert "handarbeit" in out and "(ohne Besitzer)" in out
    assert "stillgelegt seit 08.11.2026" in out


def test_list_on_empty_registry(cfg_path, clock):
    code, out, _ = run(cfg_path, clock, "list")
    assert code == 0 and "Keine Apps registriert." in out


def test_list_changes_nothing(cfg_path, env, clock):
    run(cfg_path, clock, "register")
    before = files(env)
    run(cfg_path, clock, "list")
    assert files(env) == before


# --- AK2: aktualisieren -------------------------------------------------------------------------------------------


def test_ak2_changed_manifest_of_the_same_owner_shows_up_without_restart(cfg_path, manifests, clock):
    run(cfg_path, clock, "register")
    registry = registry_for(cfg_path, manifests)
    assert registry.reload().apps["pruefung"].menu_label == "Prüfungen"
    code, out, _ = run(cfg_path, clock, "register", manifest={**GOOD, "version": "1.1.0",
                                                              "menu": {"label": "Prüfungen neu", "icon": "grades"}})
    assert code == 0 and "Aktualisiert" in out
    app = registry.refresh().apps["pruefung"]                   # dasselbe Registry-Objekt: kein Neustart
    assert (app.menu_label, app.version, app.status) == ("Prüfungen neu", "1.1.0", "registering")


# --- AK3: entfernen -----------------------------------------------------------------------------------------------


def test_ak3_remove_takes_the_app_out_of_the_registry(cfg_path, env, manifests, clock):
    run(cfg_path, clock, "register")
    registry = registry_for(cfg_path, manifests)
    assert "pruefung" in registry.reload().apps
    code, out, err = run(cfg_path, clock, "remove", "pruefung")
    assert (code, err) == (0, "") and "Stillgelegt" in out
    assert not (manifests / "pruefung.json").exists()
    assert "pruefung" not in registry.refresh().apps            # nächstes Nachladen, ohne Neustart
    assert json.loads((env / "registry" / "owners.json").read_text(encoding="utf-8")) == {"pruefung": OWNER}
    assert json.loads((env / "registry" / "retired.json").read_text(encoding="utf-8")) == {
        "pruefung": "2026-11-08T15:00:00+00:00"}


def test_ak3_same_owner_may_register_again_at_once(cfg_path, env, manifests, clock):
    run(cfg_path, clock, "register")
    run(cfg_path, clock, "remove", "pruefung")
    code, out, _ = run(cfg_path, clock, "register")
    assert code == 0 and "Neu registriert" in out
    assert (manifests / "pruefung.json").exists()
    assert json.loads((env / "registry" / "retired.json").read_text(encoding="utf-8")) == {}


def test_ak3_other_owner_is_refused_within_90_days(cfg_path, env, clock):
    run(cfg_path, clock, "register")
    run(cfg_path, clock, "remove", "pruefung")
    clock.now = T0 + timedelta(days=89)
    before = files(env)
    for command in ("check", "register"):
        code, _, err = run(cfg_path, clock, command, owner=OTHER)
        assert code == 1 and "PF-202" in err and "noch gesperrt" in err and "06.02.2027" in err
    assert files(env) == before


def test_ak3_other_owner_may_take_the_name_after_90_days(cfg_path, env, clock):
    run(cfg_path, clock, "register")
    run(cfg_path, clock, "remove", "pruefung")
    clock.now = T0 + timedelta(days=90)
    code, out, _ = run(cfg_path, clock, "register", owner=OTHER)
    assert code == 0 and "Neu registriert" in out
    assert json.loads((env / "registry" / "owners.json").read_text(encoding="utf-8")) == {"pruefung": OTHER}
    assert json.loads((env / "registry" / "retired.json").read_text(encoding="utf-8")) == {}
    assert run(cfg_path, clock, "register", owner=OWNER)[0] == 1     # der alte Besitzer hat den Namen jetzt nicht mehr


# --- AK4 und weitere Negativfälle ---------------------------------------------------------------------------------


def test_ak4_remove_of_an_unknown_slug_fails_and_changes_nothing(cfg_path, env, clock):
    run(cfg_path, clock, "register")
    before = files(env)
    code, out, err = run(cfg_path, clock, "remove", "gibtsnicht")
    assert code == 1 and out == ""
    assert "„gibtsnicht\" ist nicht registriert" in err and "Es wurde nichts geändert" in err
    assert files(env) == before


def test_remove_twice_fails_the_second_time(cfg_path, env, clock):
    run(cfg_path, clock, "register")
    assert run(cfg_path, clock, "remove", "pruefung")[0] == 0
    before = files(env)
    assert run(cfg_path, clock, "remove", "pruefung")[0] == 1
    assert files(env) == before


def test_remove_by_another_owner_is_refused(cfg_path, env, clock):
    run(cfg_path, clock, "register")
    before = files(env)
    code, _, err = run(cfg_path, clock, "remove", "pruefung", owner=OTHER)
    assert code == 1 and "PF-202" in err and "Entfernen abgelehnt" in err
    assert files(env) == before


def test_remove_of_a_hand_made_manifest_is_refused(cfg_path, env, manifests, clock):
    (manifests / "handarbeit.json").write_text(json.dumps({**GOOD, "slug": "handarbeit"}), encoding="utf-8")
    before = files(env)
    assert run(cfg_path, clock, "remove", "handarbeit")[0] == 1
    assert files(env) == before


@pytest.mark.parametrize("argv", [
    ["remove", "--owner", OWNER],                              # Name fehlt
    ["remove", "../x", "--owner", OWNER],                       # kein gültiger Name
    ["remove", "Pruefung", "--owner", OWNER],
    ["remove", "pruefung"],                                     # --owner fehlt
    ["list", "--owner", OWNER],                                 # list kennt kein --owner
    ["loeschen", "pruefung", "--owner", OWNER],
])
def test_wrong_calls_end_with_exit_2(cfg_path, argv, clock):
    err = io.StringIO()
    assert main([*argv, "--config", str(cfg_path)], io.BytesIO(b""), io.StringIO(), err, now=clock) == 2


def test_broken_retired_file_is_a_broken_operation(cfg_path, env, clock):
    run(cfg_path, clock, "register")
    (env / "registry" / "retired.json").write_text("[1, 2]", encoding="utf-8")
    code, _, err = run(cfg_path, clock, "remove", "pruefung")
    assert code == 3 and "retired.json" in err


# --- Statusdatei --------------------------------------------------------------------------------------------------


def test_status_writer_writes_on_change_and_as_heartbeat(tmp_path):
    ticks = iter([0.0, 1.0, 2.0, 40.0])
    path = tmp_path / "status.json"
    writer = StatusWriter(path, monotonic=lambda: next(ticks), wall=lambda: T0)
    app = AppView.from_manifest(GOOD, status="registering")
    snap = Snapshot(version=1, apps={"pruefung": app})
    assert writer.write(snap) is True                                  # erstes Mal
    assert writer.write(snap) is False                                 # nichts geändert, kein Heartbeat fällig
    changed = Snapshot(version=2, apps={"pruefung": AppView.from_manifest(GOOD, status="healthy")})
    assert writer.write(changed) is True                               # Status geändert
    assert writer.write(changed) is True                               # 30 s vorbei: Heartbeat
    report = read_status(path)
    assert report.written_at == T0 and report.apps["pruefung"]["status"] == "healthy"


def test_status_writer_survives_a_missing_folder(tmp_path):
    writer = StatusWriter(tmp_path / "fehlt" / "status.json")
    assert writer.write(Snapshot(version=1, apps={})) is False


@pytest.mark.parametrize("content", ["kein json", "[]", '{"written_at": "gestern", "apps": {}}',
                                     '{"written_at": "2026-11-08T15:00:00", "apps": {}}', '{"apps": {}}'])
def test_broken_status_file_reads_as_empty(tmp_path, content):
    path = tmp_path / "status.json"
    path.write_text(content, encoding="utf-8")
    report = read_status(path)
    assert report.written_at is None and report.apps == {} and report.is_stale(T0)


def test_vm_config_sets_the_status_file():
    text = (Path(__file__).resolve().parent.parent / "dev" / "gateway.vm.yml").read_text(encoding="utf-8")
    assert "status_file: /var/lib/portal/status/status.json" in text
