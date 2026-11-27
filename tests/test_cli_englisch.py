"""Der Befehl ``python -m portal.registry`` (``portal-deploy``) auf Englisch (HKA-101): Sprachwahl, Meldungen, Fehlerblöcke."""

import fcntl
import io
import json
import string
from datetime import datetime, timezone

import pytest

from portal.core.config import load_config
from portal.core.i18n import current_language
from portal.registry import ManifestValidator
from portal.registry.__main__ import main
from portal.registry.cli_texts import TEXTS, cli_language, say
from portal.registry.registration import Registrar, Rejected

OWNER = "alexandru-tatar/pruefungen"
OTHER = "jemand/anderes-repo"
GOOD = {"slug": "pruefung", "name": "Prüfungen", "name_en": "Examinations", "category": "Studium",
        "menu": {"label": "Prüfungen", "label_en": "Examinations", "icon": "grades"}, "roles": ["student"], "version": "1.0.0"}
T0 = datetime(2026, 11, 8, 15, 0, 0, tzinfo=timezone.utc)
EN = {"PORTAL_LANG": "en"}


@pytest.fixture
def cfg_path(env):
    path = env / "gateway.dev.yml"
    (env / "registry").mkdir()
    path.write_text(path.read_text(encoding="utf-8") + "\nregistry:\n  owners_file: registry/owners.json\n", encoding="utf-8")
    return path


def run(cfg_path, command, manifest=None, owner=OWNER, slug=None, env=EN):
    raw = b"" if manifest is None else (manifest if isinstance(manifest, bytes) else json.dumps(manifest).encode())
    argv = [command] + ([slug] if slug else []) + ["--config", str(cfg_path)] + ([] if command == "list" else ["--owner", owner])
    out, err = io.StringIO(), io.StringIO()
    code = main(argv, io.BytesIO(raw), out, err, now=lambda: T0, env=env)
    return code, out.getvalue(), err.getvalue()


@pytest.mark.parametrize("env, expected", [
    ({}, "de"), ({"PORTAL_LANG": "en"}, "en"), ({"PORTAL_LANG": "de", "LANG": "en_US.UTF-8"}, "de"),
    ({"PORTAL_LANG": "fr", "LANG": "en_US.UTF-8"}, "en"), ({"LANG": "en_US.UTF-8"}, "en"), ({"LANG": "en_GB"}, "en"),
    ({"LANG": "de_DE.UTF-8"}, "de"), ({"LC_ALL": "C", "LANG": "en_US.UTF-8"}, "de"),
    ({"LC_ALL": "en_US.UTF-8", "LANG": "de_DE.UTF-8"}, "en"), ({"LC_MESSAGES": "en_US", "LANG": "de_DE"}, "en"),
    ({"LANG": ""}, "de"), ({"LANG": "POSIX"}, "de"),
])
def test_cli_language(env, expected):
    assert cli_language(env) == expected


def test_german_stays_the_default(cfg_path):
    code, out, err = run(cfg_path, "check", GOOD, env={})
    assert (code, err) == (0, "") and "Das Manifest ist gültig." in out


def test_check_and_register_in_english(cfg_path):
    code, out, err = run(cfg_path, "check", GOOD)
    assert (code, err) == (0, "") and out.strip() == "OK slug=pruefung version=1.0.0: The manifest is valid."
    assert "Newly registered" in run(cfg_path, "register", GOOD)[1]
    assert "Updated" in run(cfg_path, "register", {**GOOD, "version": "1.1.0"})[1]


def test_pf104_block_in_english_names_the_missing_english_fields(cfg_path):
    manifest = {k: v for k, v in GOOD.items() if k != "name_en"}
    code, out, err = run(cfg_path, "register", manifest)
    assert (code, out) == (1, "")
    for text in ("ERROR PF-104  –  manifest.json invalid", "What happened:", "Why it matters:", "What to do:",
                 "Technical details:", "Allowed roles:", "Allowed categories:", "'name_en' is a required property"):
        assert text in err, text
    assert "FEHLER" not in err and "Was ist passiert" not in err


def test_pf104_not_json_and_too_big_in_english(cfg_path):
    assert "The file is not valid JSON." in run(cfg_path, "check", b"{kaputt")[2]
    assert "The file is larger than 64 KiB." in run(cfg_path, "check", b" " * 70000)[2]


def test_pf202_other_owner_in_english(cfg_path):
    run(cfg_path, "register", GOOD)
    code, _, err = run(cfg_path, "register", GOOD, owner=OTHER)
    assert code == 1 and "Registration rejected" in err and 'The name "pruefung" belongs to another repository.' in err
    assert 'Choose a different slug than "pruefung"' in err


def test_pf202_locked_name_uses_english_dates(cfg_path):
    run(cfg_path, "register", GOOD)
    run(cfg_path, "remove", owner=OWNER, slug="pruefung")
    err = run(cfg_path, "register", GOOD, owner=OTHER)[2]
    assert "still blocked" in err and "retired on 2026-11-08" in err and "(90 days)" in err


def test_remove_in_english(cfg_path):
    run(cfg_path, "register", GOOD)
    code, out, _ = run(cfg_path, "remove", owner=OTHER, slug="pruefung")
    assert code == 1 and "Removal rejected" in _
    code, out, err = run(cfg_path, "remove", owner=OWNER, slug="pruefung")
    assert code == 0 and "Retired." in out
    code, _, err = run(cfg_path, "remove", owner=OWNER, slug="pruefung")
    assert code == 1 and 'The app "pruefung" is not registered. Nothing was changed.' in err and "portal-deploy list" in err


def test_list_in_english(cfg_path):
    code, out, _ = run(cfg_path, "list")
    assert code == 0 and "(no owner)" in out and "unknown" in out and "No status file found" in out
    run(cfg_path, "register", GOOD)
    out = run(cfg_path, "list")[1]
    assert "SLUG" in out and "OWNER" in out and "LAST CHECK" in out and "pruefung" in out
    run(cfg_path, "remove", owner=OWNER, slug="pruefung")
    assert "retired since 2026-11-08" in run(cfg_path, "list")[1]


def test_configuration_errors_in_english(cfg_path, tmp_path):
    code, _, err = run(tmp_path / "missing.yml", "list")
    assert code == 3 and err.startswith("ERROR configuration:")


def test_help_in_english(cfg_path, capsys):
    assert main(["--help"], env=EN) == 0     # argparse beendet bei --help; ``main`` fängt das ab
    assert "Show all apps with owner and status" in capsys.readouterr().out


def test_pf204_in_english(cfg_path, env, tmp_path):
    cfg = load_config(cfg_path)
    registrar = Registrar(env / "manifests", cfg.registry.owners_file,
                          ManifestValidator(cfg.schema_path, cfg.role_vocabulary, cfg.adapter_scopes),
                          cfg.role_vocabulary, lock_timeout=0.3)
    token = current_language.set("en")
    try:
        with open(cfg.registry.owners_file.with_name("owners.json.lock"), "a") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            with pytest.raises(Rejected) as caught:
                registrar.register(json.dumps(GOOD).encode(), OWNER)
        assert "Deployment locked" in caught.value.render() and "Wait a few seconds" in caught.value.render()
    finally:
        current_language.reset(token)


def test_language_does_not_leak_after_main(cfg_path):
    run(cfg_path, "check", GOOD)
    assert current_language.get() == "de"
    assert say("ok.updated") == "Aktualisiert"


def test_same_keys_and_placeholders_in_both_languages():
    assert set(TEXTS["de"]) == set(TEXTS["en"])
    fields = lambda text: {name for _, name, _, _ in string.Formatter().parse(text) if name}  # noqa: E731
    assert {k: (fields(TEXTS["de"][k]), fields(TEXTS["en"][k])) for k in TEXTS["de"]
            if fields(TEXTS["de"][k]) != fields(TEXTS["en"][k])} == {}


def test_english_texts_are_not_copies_of_german():
    allowed = {"list.slug", "list.version", "list.status", "arg.owner_form"}
    same = [k for k in TEXTS["de"] if TEXTS["de"][k] == TEXTS["en"][k] and k not in allowed]
    assert same == []


def test_remove_refused_detail_in_english(cfg_path):
    run(cfg_path, "register", GOOD)
    code, _, err = run(cfg_path, "remove", owner=OTHER, slug="pruefung")
    assert code == 1 and f"slug=pruefung requested by {OTHER}, bound to another repository" in err
    assert "angefragt von" not in err
