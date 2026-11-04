"""Registrierung aus der Pipeline: ``python -m portal.registry check|register`` (HKA-53, AK3 und AK4)."""

import io
import json
import os
import stat
from pathlib import Path

import pytest
import yaml

from portal.core.config import ConfigError, load_config
from portal.registry import ManifestDirectorySource, ManifestValidator, Registry
from portal.registry.__main__ import main
from portal.registry.registration import Registrar, Rejected, fcntl

ROOT = Path(__file__).resolve().parent.parent
OWNER = "alexandru-tatar/pruefungen"
GOOD = {"slug": "pruefung", "name": "Prüfungen", "category": "Studium",
        "menu": {"label": "Prüfungen", "icon": "grades"}, "roles": ["student"], "version": "1.0.0"}


@pytest.fixture
def cfg_path(env) -> Path:
    """Konfiguration mit Besitzerdatei in einem eigenen Ordner; der Manifest-Ordner enthält die Beispiel-Apps."""
    path = env / "gateway.dev.yml"
    (env / "registry").mkdir()
    path.write_text(path.read_text(encoding="utf-8") + "\nregistry:\n  owners_file: registry/owners.json\n",
                    encoding="utf-8")
    return path


@pytest.fixture
def manifests(env) -> Path:
    return env / "manifests"


def snapshot(folder: Path) -> dict[str, bytes]:
    """Alle Dateien samt Inhalt; die leere Sperrdatei zählt nicht, sie entsteht bei jeder Registrierung."""
    return {str(p.relative_to(folder)): p.read_bytes() for p in sorted(folder.rglob("*"))
            if p.is_file() and not p.name.endswith(".lock")}


def run(cfg_path, command, manifest, owner=OWNER):
    """Den Befehl mit dem Manifest auf der Standardeingabe aufrufen.

    :return: Exit-Code, Standardausgabe, Fehlerausgabe
    """
    raw = manifest if isinstance(manifest, bytes) else json.dumps(manifest).encode()
    out, err = io.StringIO(), io.StringIO()
    code = main([command, "--config", str(cfg_path), "--owner", owner], io.BytesIO(raw), out, err)
    return code, out.getvalue(), err.getvalue()


def test_register_writes_manifest_and_binds_owner(cfg_path, env, manifests):
    code, out, err = run(cfg_path, "register", GOOD)
    assert (code, err) == (0, "")
    assert "Neu registriert" in out and "slug=pruefung" in out
    assert json.loads((manifests / "pruefung.json").read_text(encoding="utf-8")) == GOOD
    assert json.loads((env / "registry" / "owners.json").read_text(encoding="utf-8")) == {"pruefung": OWNER}
    assert stat.S_IMODE((manifests / "pruefung.json").stat().st_mode) == 0o644      # das Portal liest als anderer Benutzer
    assert [p.name for p in manifests.iterdir() if p.name.endswith(".tmp")] == []


def test_registered_manifest_is_taken_over_by_the_registry_as_registering(cfg_path, env, manifests):
    assert run(cfg_path, "register", GOOD)[0] == 0
    cfg = load_config(cfg_path)
    source = ManifestDirectorySource(manifests, ManifestValidator(cfg.schema_path, cfg.role_vocabulary, cfg.adapter_scopes),
                                     probe=True)
    app = Registry(source, keep_status=True).reload().apps["pruefung"]
    assert app.status == "registering" and app.roles == {"student"} and app.last_deployed_at.endswith(" UTC")


def test_register_again_by_the_same_owner_updates(cfg_path, manifests):
    run(cfg_path, "register", GOOD)
    code, out, _ = run(cfg_path, "register", {**GOOD, "version": "1.1.0"})
    assert code == 0 and "Aktualisiert" in out
    assert json.loads((manifests / "pruefung.json").read_text(encoding="utf-8"))["version"] == "1.1.0"


def test_check_is_valid_and_writes_nothing(cfg_path, env, manifests):
    before = snapshot(env)
    code, out, err = run(cfg_path, "check", GOOD)
    assert (code, err) == (0, "") and "gültig" in out
    assert snapshot(env) == before


@pytest.mark.parametrize("change, pointer, text", [
    ({"roles": ["student", "dean"]}, "/roles", "unknown role 'dean'"),
    ({"category": "Freizeit"}, "/category", "Freizeit"),
    ({"slug": "admin"}, "/slug", "reserved"),
    ({"slug": "Kein Slug"}, "/slug", ""),
    ({"menu": {"label": "x", "icon": "tür"}}, "/menu/icon", ""),
    ({"version": "1.0"}, "/version", ""),
    ({"adapters": ["mail:senden"]}, "/adapters", "unknown adapter scope"),
    ({"zusatz": 1}, "/", "zusatz"),
])
def test_ak3_invalid_manifest_is_rejected_with_pf104_and_names_the_field(cfg_path, env, change, pointer, text):
    before = snapshot(env)
    code, out, err = run(cfg_path, "register", {**GOOD, **change})
    assert code == 1 and out == ""
    assert "FEHLER PF-104" in err and "manifest.json ungültig" in err
    assert pointer in err and text in err
    assert "Erlaubte Rollen: student, employee, professor" in err and "Erlaubte Kategorien: Studium" in err
    assert snapshot(env) == before                     # nichts registriert, Menüstand unverändert


def test_ak3_missing_field_and_not_json_and_too_large(cfg_path, env):
    before = snapshot(env)
    without_roles = {k: v for k, v in GOOD.items() if k != "roles"}
    for raw, needle in [(without_roles, "roles"), (b"{kaputt", "kein gültiges JSON"), (b"\xff\xfe", "kein gültiges JSON"),
                        (b"[]", "is not of type 'object'"), (b" " * 70_000, "64 KiB")]:
        code, _, err = run(cfg_path, "register", raw)
        assert code == 1 and "PF-104" in err and needle in err, needle
    assert snapshot(env) == before


def test_error_block_has_the_catalog_format(cfg_path):
    _, _, err = run(cfg_path, "register", {**GOOD, "roles": ["dean"]})
    lines = err.splitlines()
    assert lines[0] == lines[-1] == "=" * 60
    assert lines[1].startswith("FEHLER PF-104  –  ")
    heads = [line.split(":")[0] for line in lines if line.split(":")[0] in
             ("Was ist passiert", "Warum wichtig", "Was tun", "Technische Details")]
    assert heads == ["Was ist passiert", "Warum wichtig", "Was tun", "Technische Details"]
    assert any(line.startswith("Was tun:") and "1. " in line for line in lines)


def test_ak4_slug_of_another_repository_is_rejected(cfg_path, env, manifests):
    run(cfg_path, "register", GOOD)
    before = snapshot(env)
    code, out, err = run(cfg_path, "register", {**GOOD, "name": "Fremde App", "version": "9.0.0"}, owner="anderer/fremd")
    assert code == 1 and out == ""
    assert "FEHLER PF-202" in err and "Registrierung abgelehnt" in err and "„pruefung“" in err.replace('"', "“")
    assert snapshot(env) == before                     # die erste App bleibt, wie sie war
    assert run(cfg_path, "check", GOOD, owner="anderer/fremd")[0] == 1


def test_ak4_slug_of_a_hand_placed_manifest_is_rejected(cfg_path, env):
    before = snapshot(env)
    code, _, err = run(cfg_path, "register", {**GOOD, "slug": "noten"})       # dev/manifests/noten.json
    assert code == 1 and "PF-202" in err and "von Hand eingerichtet" in err
    assert snapshot(env) == before


def test_ak4_slug_in_a_second_file_is_rejected(cfg_path, env, manifests):
    (manifests / "zz-kopie.json").write_text(json.dumps(GOOD), encoding="utf-8")
    code, _, err = run(cfg_path, "register", GOOD)
    assert code == 1 and "PF-202" in err and "zz-kopie.json" in err
    assert not (manifests / "pruefung.json").exists()


@pytest.mark.skipif(fcntl is None, reason="Sperre nur unter Linux und macOS")
def test_second_registration_at_the_same_time_gets_pf204(cfg_path, env, manifests):
    cfg = load_config(cfg_path)
    registrar = Registrar(manifests, cfg.registry.owners_file,
                          ManifestValidator(cfg.schema_path, cfg.role_vocabulary, cfg.adapter_scopes),
                          cfg.role_vocabulary, lock_timeout=0.3)
    with open(cfg.registry.owners_file.with_name("owners.json.lock"), "a") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        with pytest.raises(Rejected) as caught:
            registrar.register(json.dumps(GOOD).encode(), OWNER)
    assert caught.value.code == "PF-204" and "gesperrt" in caught.value.render()
    assert not (manifests / "pruefung.json").exists()
    registrar.register(json.dumps(GOOD).encode(), OWNER)             # Sperre frei: geht


def test_exit_codes_for_wrong_call_and_broken_operation(cfg_path, env, tmp_path):
    for argv in (["register"], ["register", "--config", str(cfg_path)], ["löschen", "--config", "x", "--owner", OWNER],
                 ["register", "--config", str(cfg_path), "--owner", "ohne-schrägstrich"],
                 ["register", "--config", str(cfg_path), "--owner", "a/b; id"]):
        assert main(argv, io.BytesIO(b"{}"), io.StringIO(), io.StringIO()) == 2, argv
    err = io.StringIO()
    assert main(["check", "--config", str(tmp_path / "gibt-es-nicht.yml"), "--owner", OWNER], io.BytesIO(b"{}"),
                io.StringIO(), err) == 3 and "Konfiguration" in err.getvalue()
    (env / "registry" / "owners.json").write_text("[1, 2]", encoding="utf-8")
    code, _, err_text = run(cfg_path, "register", GOOD)
    assert code == 3 and "Besitzerdatei" in err_text and "Plattform-Team" in err_text


def test_config_without_owners_file_is_a_broken_operation(env):
    err = io.StringIO()
    code = main(["register", "--config", str(env / "gateway.dev.yml"), "--owner", OWNER], io.BytesIO(b"{}"),
                io.StringIO(), err)
    assert code == 3 and "owners_file" in err.getvalue()


def test_no_leftover_files_when_writing_fails(cfg_path, env, manifests):
    os.chmod(manifests, 0o555)
    try:
        if os.access(manifests, os.W_OK):
            pytest.skip("läuft als Benutzer, der trotzdem schreiben darf")
        code, _, err = run(cfg_path, "register", GOOD)
        assert code == 3 and "Schreiben nicht möglich" in err
    finally:
        os.chmod(manifests, 0o755)
    assert [p.name for p in manifests.iterdir() if p.name.startswith(".")] == []
    # Besitzerdatei wird zuerst geschrieben: der Name ist für denselben Besitzer weiter frei
    assert run(cfg_path, "register", GOOD)[0] == 0


def test_vm_config_loads_with_probe_registry_and_gateway(env, kit_dist):
    """``dev/gateway.vm.yml`` ist gültig (Pfade der VM durch die Testkopie ersetzt)."""
    (env / "vm-manifests").mkdir()
    text = (env / "gateway.vm.yml").read_text(encoding="utf-8")
    text = text.replace("/var/lib/portal/manifests", str(env / "vm-manifests"))
    text = text.replace("../schemas/manifest.schema.json", str(ROOT / "schemas" / "manifest.schema.json"))
    text = text.replace("../kit/dist", str(kit_dist))
    (env / "gateway.vm.yml").write_text(text, encoding="utf-8")
    cfg = load_config(env / "gateway.vm.yml")
    assert cfg.registry.probe and cfg.registry.refresh_seconds == 5
    assert cfg.registry.owners_file == Path("/var/lib/portal/registry/owners.json").resolve()
    assert cfg.state_file is None and cfg.apps.upstream_for("noten") == "http://app-noten:8080"
    assert cfg.assertion.issuer == "https://iwi-hean-05.hs-karlsruhe.de/"


@pytest.mark.parametrize("section, message", [
    ({"probe": True}, "probe needs an apps section"),
    ({"probe": "ja"}, "probe must be true or false"),
    ({"refresh_seconds": 0}, "at least 1"),
    ({"unbekannt": 1}, "unknown registry key"),
])
def test_registry_section_is_checked(env, section, message):
    path = env / "gateway.dev.yml"
    path.write_text(path.read_text(encoding="utf-8") + "\n" + yaml.safe_dump({"registry": section}), encoding="utf-8")
    with pytest.raises(ConfigError, match=message):
        load_config(path)


def test_probe_excludes_state_file(env):
    path = env / "gateway.dev.yml"            # enthält state_file
    path.write_text(path.read_text(encoding="utf-8") + "\nassertion:\n  issuer: x\napps:\n  upstream: http://a-{slug}:1\n"
                    "registry:\n  probe: true\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="remove state_file"):
        load_config(path)
