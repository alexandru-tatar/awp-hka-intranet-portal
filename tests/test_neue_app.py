"""Tests für tools/neue-app.sh (HKA-54) mit einer Attrappe für die GitHub-CLI (tests/fixtures/fake-gh/gh)."""

import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from portal.registry.models import RESERVED_SLUGS

ROOT = Path(__file__).resolve().parent.parent
SKRIPT = ROOT / "tools" / "neue-app.sh"
FAKE_BIN = ROOT / "tests" / "fixtures" / "fake-gh"

pytestmark = pytest.mark.skipif(shutil.which("jq") is None, reason="jq fehlt")

VORLAGE_MANIFEST = """{
  "slug": "meine-app",
  "name": "Meine App",
  "category": "Sonstiges",
  "menu": { "label": "Meine App", "icon": "info" },
  "roles": ["student"],
  "version": "0.1.0"
}
"""
# Zugangsdaten, die im Testlauf in der Umgebung stehen. Sie dürfen nirgends im Log landen (AK4).
# Aufbau wie ein echtes GitHub-Token; der Wert ist erfunden.
ERFUNDENES_TOKEN = "ghp_" + "Zx3Qw9Lm2Vb7Nc5Kd8Fh1Jg4Ts6Ra0Pe9Yu"
GITLEAKS = "zricethezav/gitleaks:v8.30.1"


def manifest(slug: str) -> str:
    return json.dumps({"slug": slug, "name": slug, "category": "Studium", "menu": {"label": slug, "icon": "info"},
                       "roles": ["student"], "version": "1.0.0"})


@pytest.fixture
def umgebung(tmp_path):
    """Zustand der Attrappe, Logdatei, Geheimnis-Dateien und die Umgebung für das Skript."""
    zustand = {
        "login": "alexandru-tatar",
        "portal": "awp-hka-intranet-portal",
        "manifeste": {"noten.json": manifest("noten"), "stundenplan.json": manifest("stundenplan")},
        "mitglieder": ["alexandru-tatar", "thanhxt", "krya1012"],
        "apps": {"app-bestehend": manifest("bestehend")},
        "vorlagen": {
            "awp-hka-gold-js": {"is_template": True, "workflow": True, "manifest": VORLAGE_MANIFEST},
            "awp-hka-gold-python": {"is_template": True, "workflow": True, "manifest": VORLAGE_MANIFEST},
        },
        "repos": {},
    }
    state_pfad = tmp_path / "state.json"
    log_pfad = tmp_path / "log.jsonl"
    state_pfad.write_text(json.dumps(zustand))
    env = {
        **os.environ,
        "PATH": f"{FAKE_BIN}{os.pathsep}{os.environ['PATH']}",
        "FAKE_GH_STATE": str(state_pfad),
        "FAKE_GH_LOG": str(log_pfad),
        "NEUE_APP_WARTEN": "0",
    }
    for name in ("OWNER", "VORLAGE_OWNER", "PORTAL_REPO"):
        env.pop(name, None)

    class Umgebung:
        pass

    u = Umgebung()
    u.env = env
    u.state_pfad = state_pfad
    u.log_pfad = log_pfad

    def zustand_lesen():
        return json.loads(state_pfad.read_text())

    def zustand_aendern(aenderung):
        z = zustand_lesen()
        aenderung(z)
        state_pfad.write_text(json.dumps(z))

    def log():
        if not log_pfad.exists():
            return []
        return [json.loads(z) for z in log_pfad.read_text().splitlines()]

    def starte(*argumente, **env_zusatz):
        return subprocess.run(["bash", str(SKRIPT), *argumente], env={**env, **env_zusatz}, capture_output=True,
                              text=True, stdin=subprocess.DEVNULL, timeout=60)

    u.zustand = zustand_lesen
    u.aendern = zustand_aendern
    u.log = log
    u.starte = starte
    return u


def veraendernde_aufrufe(log):
    """Aufrufe, die etwas anlegen oder ändern (alles außer lesenden GET-Abfragen)."""
    return [e for e in log if e.get("aktion") in ("repo create", "repo edit")
            or (e.get("aktion") == "api" and e["methode"] != "GET")]


def reihenfolge(log, methode, endpunkt_ende):
    for i, e in enumerate(log):
        if e.get("aktion") == "api" and e["methode"] == methode and e["endpunkt"].endswith(endpunkt_ende):
            return i
    raise AssertionError(f"Aufruf {methode} …{endpunkt_ende} fehlt im Log")


def test_gueltiger_slug_ohne_anlegen(umgebung):
    r = umgebung.starte("noten-uebersicht", "js", "--pruefen")
    assert r.returncode == 0, r.stderr
    assert "Alle Prüfungen bestanden." in r.stdout
    assert "app-noten-uebersicht" in r.stdout
    assert veraendernde_aufrufe(umgebung.log()) == []


@pytest.mark.parametrize("slug", ["Ab", "1abc", "ab", "a" * 32, "mit_unterstrich", "gross-Buchstabe", "ab x"])
def test_ungueltiger_slug(umgebung, slug):
    r = umgebung.starte(slug, "js")
    assert r.returncode == 1
    assert "ungültig" in r.stderr
    assert veraendernde_aufrufe(umgebung.log()) == []


@pytest.mark.parametrize("slug", ["admin", "healthz", "meine-app", "andere-app"])
def test_reservierter_oder_gesperrter_slug(umgebung, slug):
    r = umgebung.starte(slug, "python")
    assert r.returncode == 1
    assert "FEHLER" in r.stderr and slug in r.stderr
    assert veraendernde_aufrufe(umgebung.log()) == []


def test_unbekannte_sprache(umgebung):
    r = umgebung.starte("meine-noten", "go")
    assert r.returncode == 1
    assert "js oder python" in r.stderr
    assert veraendernde_aufrufe(umgebung.log()) == []


def test_unbekannte_option(umgebung):
    r = umgebung.starte("-anfang", "js")
    assert r.returncode == 1
    assert "Unbekannte Option" in r.stderr
    assert veraendernde_aufrufe(umgebung.log()) == []


def test_falsche_argumentzahl(umgebung):
    r = umgebung.starte("nur-ein-argument")
    assert r.returncode == 1
    assert "Aufruf:" in r.stderr


def test_repository_gibt_es_schon(umgebung):
    r = umgebung.starte("bestehend", "js")
    assert r.returncode == 1
    assert "gibt es schon" in r.stderr
    assert veraendernde_aufrufe(umgebung.log()) == []


def test_slug_im_portal_vergeben(umgebung):
    r = umgebung.starte("noten", "js")
    assert r.returncode == 1
    assert "gehört schon zu einer anderen App" in r.stderr
    assert veraendernde_aufrufe(umgebung.log()) == []


def test_slug_in_anderer_app_vergeben(umgebung):
    # Anderer Repository-Name, aber derselbe Slug im manifest.json.
    umgebung.aendern(lambda z: z["apps"].update({"app-anders-benannt": manifest("doppelt")}))
    r = umgebung.starte("doppelt", "js")
    assert r.returncode == 1
    assert "gehört schon zu einer anderen App" in r.stderr
    assert veraendernde_aufrufe(umgebung.log()) == []


def test_vorlage_nicht_markiert(umgebung):
    umgebung.aendern(lambda z: z["vorlagen"]["awp-hka-gold-js"].update({"is_template": False}))
    r = umgebung.starte("meine-noten", "js")
    assert r.returncode == 1
    assert "gh repo edit alexandru-tatar/awp-hka-gold-js --template" in r.stderr
    assert veraendernde_aufrufe(umgebung.log()) == []


def test_vorlage_ohne_workflow_warnt(umgebung):
    umgebung.aendern(lambda z: z["vorlagen"]["awp-hka-gold-js"].update({"workflow": False}))
    r = umgebung.starte("meine-noten", "js", "--pruefen")
    assert r.returncode == 0
    assert "WARNUNG" in r.stderr and "pruefung.yml" in r.stderr


def test_falscher_gh_benutzer(umgebung):
    umgebung.aendern(lambda z: z.update({"login": "krya1012"}))
    r = umgebung.starte("meine-noten", "js")
    assert r.returncode == 1
    assert "Konto-Inhaber" in r.stderr
    assert veraendernde_aufrufe(umgebung.log()) == []


def test_anlegen_komplett(umgebung):
    r = umgebung.starte("noten-uebersicht", "js")
    assert r.returncode == 0, r.stderr
    log = umgebung.log()
    repo = "alexandru-tatar/app-noten-uebersicht"

    # 1. Repository aus der Vorlage, öffentlich
    anlegen = next(e for e in log if e.get("aktion") == "repo create")
    assert anlegen["repo"] == repo
    assert "--public" in anlegen["argv"]
    assert anlegen["argv"][anlegen["argv"].index("--template") + 1] == "alexandru-tatar/awp-hka-gold-js"

    # 2. Slug im manifest.json, sonst nichts verändert
    put = next(e for e in log if e.get("aktion") == "api" and e["methode"] == "PUT" and e["endpunkt"].endswith("contents/manifest.json"))
    inhalt = base64.b64decode(next(a for a in put["argv"] if a.startswith("content=")).split("=", 1)[1]).decode()
    assert inhalt == VORLAGE_MANIFEST.replace('"meine-app"', '"noten-uebersicht"')
    assert "branch=main" in put["argv"]

    # 3. develop, Thema, Collaborators (ohne den Konto-Inhaber)
    zustand = umgebung.zustand()
    assert zustand["repos"]["app-noten-uebersicht"]["branches"] == ["main", "develop"]
    assert any(e.get("aktion") == "repo edit" and "hka-app" in e["argv"] for e in log)
    eingeladen = {e["endpunkt"].rsplit("/", 1)[1] for e in log if e.get("aktion") == "api" and "/collaborators/" in e["endpunkt"]}
    assert eingeladen == {"thanhxt", "krya1012"}
    assert all("permission=push" in e["argv"] for e in log if e.get("aktion") == "api" and "/collaborators/" in e["endpunkt"])

    # 4. Ruleset: 1 Freigabe, Pflicht-Check "check", keine Ausnahme
    ruleset = next(e for e in log if e.get("aktion") == "api" and e["endpunkt"].endswith("/rulesets"))
    payload = json.loads(ruleset["stdin"])
    assert payload["enforcement"] == "active"
    assert payload["bypass_actors"] == []
    assert payload["conditions"]["ref_name"]["include"] == ["refs/heads/main"]
    regeln = {r["type"]: r.get("parameters") for r in payload["rules"]}
    assert regeln["pull_request"]["required_approving_review_count"] == 1
    assert regeln["pull_request"]["require_last_push_approval"] is True
    assert [c["context"] for c in regeln["required_status_checks"]["required_status_checks"]] == ["check"]
    assert {"deletion", "non_fast_forward"} <= set(regeln)

    # Reihenfolge: Slug und develop vor dem Ruleset (danach ist kein Push auf main mehr möglich)
    i_ruleset = reihenfolge(log, "POST", "/rulesets")
    assert reihenfolge(log, "PUT", "contents/manifest.json") < i_ruleset
    assert reihenfolge(log, "POST", "git/refs") < i_ruleset

    assert "Fertig" in r.stdout


def test_ohne_team_keine_einladungen(umgebung):
    r = umgebung.starte("noten-uebersicht", "js", "--ohne-team")
    assert r.returncode == 0, r.stderr
    log = umgebung.log()
    assert not any(e.get("aktion") == "api" and "collaborators" in e["endpunkt"] for e in log)
    assert "--ohne-team" in r.stdout
    # Alles andere bleibt: develop und Ruleset.
    reihenfolge(log, "POST", "/rulesets")
    assert umgebung.zustand()["repos"]["app-noten-uebersicht"]["branches"] == ["main", "develop"]


def test_ohne_team_im_plan(umgebung):
    r = umgebung.starte("noten-uebersicht", "js", "--pruefen", "--ohne-team")
    assert r.returncode == 0, r.stderr
    assert "Keine Collaborators (--ohne-team)" in r.stdout
    assert "Collaborators aus" not in r.stdout


def test_portal_owner_getrennt_vom_owner(umgebung):
    # Testlauf unter eigenem Konto: Portal und Golden Master liegen bei einem anderen Konto.
    umgebung.aendern(lambda z: z.update({"login": "krya1012"}))
    r = umgebung.starte("noten-uebersicht", "js", "--pruefen", OWNER="krya1012", VORLAGE_OWNER="krya1012",
                        PORTAL_OWNER="alexandru-tatar")
    assert r.returncode == 0, r.stderr
    portal = [e["endpunkt"] for e in umgebung.log() if e.get("aktion") == "api" and "dev/manifests" in e["endpunkt"]]
    assert portal and all(p.startswith("repos/alexandru-tatar/") for p in portal)


def test_kein_secret_und_kein_environment(umgebung):
    # Das Deployment läuft von Hand per scp (HKA-50, HKA-53): keine Secrets, keine Environments, keine DEPLOY_*-Pflicht.
    r = umgebung.starte("noten-uebersicht", "python")
    assert r.returncode == 0, r.stderr
    log = umgebung.log()
    assert not any(e["argv"][:1] == ["secret"] for e in log)
    assert not any("environments" in e.get("endpunkt", "") for e in log)
    assert "DEPLOY" not in r.stdout + r.stderr
    assert "secret" not in r.stdout.lower()


def test_ak4_log_ohne_zugangsdaten_gitleaks(umgebung):
    """AK4: Weder die Ausgabe noch das Log des Skripts enthält Zugangsdaten (Gitleaks)."""
    if shutil.which("docker") is None or subprocess.run(["docker", "info"], capture_output=True).returncode != 0:
        pytest.skip("Docker läuft nicht: Gitleaks-Prüfung nicht möglich")
    # Das Token steht in der Umgebung des Skripts, wie bei einem angemeldeten gh. Es darf nirgends ausgegeben werden.
    r = umgebung.starte("noten-uebersicht", "js", GH_TOKEN=ERFUNDENES_TOKEN, GITHUB_TOKEN=ERFUNDENES_TOKEN)
    assert r.returncode == 0, r.stderr
    # Unter dem Repository, nicht unter /private/tmp: Colima teilt nur das Home-Verzeichnis mit der VM.
    basis = ROOT / ".pytest_cache"
    basis.mkdir(exist_ok=True)
    ordner = Path(tempfile.mkdtemp(prefix="gitleaks-", dir=basis))
    try:
        (ordner / "ausgabe.log").write_text(r.stdout + "\n--- stderr ---\n" + r.stderr, encoding="utf-8")
        shutil.copy(umgebung.log_pfad, ordner / "gh-aufrufe.jsonl")
        # Schutz gegen eine Prüfung, die nichts liest: ein absichtlich eingebautes Token muss gefunden werden.
        probe = ordner / "probe"
        probe.mkdir()
        (probe / "probe.txt").write_text(f"token = {ERFUNDENES_TOKEN}\n", encoding="utf-8")
        scan = ["docker", "run", "--rm", "-v", f"{ordner}:/repo:ro", GITLEAKS, "dir"]
        # Die Probe muss anschlagen, sonst ist der Scanner blind.
        gefunden = subprocess.run([*scan, "/repo/probe", "--no-banner", "--no-color", "--redact"], capture_output=True, text=True)
        assert gefunden.returncode != 0, "Gitleaks hat das Probe-Token nicht gefunden: Prüfung ungültig"
        assert "leaks found" in gefunden.stdout + gefunden.stderr
        shutil.rmtree(probe)
        sauber = subprocess.run([*scan, "/repo", "--no-banner", "--no-color", "--redact"], capture_output=True, text=True)
        ausgabe = sauber.stdout + sauber.stderr
        assert sauber.returncode == 0, ausgabe
        assert "no leaks found" in ausgabe
        assert "scanned ~0 bytes" not in ausgabe, "Gitleaks hat nichts gelesen: Prüfung ungültig"
    finally:
        shutil.rmtree(ordner, ignore_errors=True)
    assert ERFUNDENES_TOKEN not in r.stdout + r.stderr + umgebung.log_pfad.read_text()


def test_wartet_auf_kopierte_vorlage(umgebung):
    umgebung.aendern(lambda z: z.update({"verzoegerung": 3}))
    r = umgebung.starte("noten-uebersicht", "js")
    assert r.returncode == 0, r.stderr
    abfragen = [e for e in umgebung.log() if e.get("aktion") == "api" and e["methode"] == "GET"
                and e["endpunkt"] == "repos/alexandru-tatar/app-noten-uebersicht/contents/manifest.json"]
    assert len(abfragen) >= 4


def test_abbruch_nennt_aufraeumbefehl(umgebung):
    umgebung.aendern(lambda z: z.update({"fehler_bei": "rulesets"}))
    r = umgebung.starte("noten-uebersicht", "js")
    assert r.returncode != 0
    assert "Ruleset" in r.stderr
    assert "gh repo delete alexandru-tatar/app-noten-uebersicht" in r.stderr
    # Gelöscht wird nie automatisch.
    assert not any(" ".join(e["argv"]).startswith("repo delete") for e in umgebung.log())


def test_reservierte_slugs_wie_im_portal():
    text = SKRIPT.read_text(encoding="utf-8")
    liste = re.search(r'^RESERVIERT="([^"]+)"$', text, re.MULTILINE)
    assert liste, "RESERVIERT fehlt im Skript"
    assert set(liste.group(1).split()) == set(RESERVED_SLUGS)


def test_slugmuster_wie_im_schema():
    schema = json.loads((ROOT / "schemas" / "manifest.schema.json").read_text(encoding="utf-8"))
    muster = schema["properties"]["slug"]["pattern"]
    assert f"SLUG_MUSTER='{muster}'" in SKRIPT.read_text(encoding="utf-8")
