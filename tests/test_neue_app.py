"""Tests für tools/neue-app.sh (HKA-54) mit einer Attrappe für die GitHub-CLI (tests/fixtures/fake-gh/gh)."""

import base64
import json
import os
import re
import shutil
import subprocess
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
GEHEIMER_SCHLUESSEL = "TOPSECRET-KEY-4711"
GEHEIMER_HOST_EINTRAG = "TOPSECRET-KNOWN-HOSTS-4712"


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
    schluessel = tmp_path / "id_deploy"
    schluessel.write_text(GEHEIMER_SCHLUESSEL + "\n")
    hosts = tmp_path / "known_hosts"
    hosts.write_text(GEHEIMER_HOST_EINTRAG + "\n")
    state_pfad.write_text(json.dumps(zustand))
    env = {
        **os.environ,
        "PATH": f"{FAKE_BIN}{os.pathsep}{os.environ['PATH']}",
        "FAKE_GH_STATE": str(state_pfad),
        "FAKE_GH_LOG": str(log_pfad),
        "DEPLOY_SSH_KEY_FILE": str(schluessel),
        "DEPLOY_KNOWN_HOSTS_FILE": str(hosts),
        "NEUE_APP_WARTEN": "0",
    }
    for name in ("OWNER", "VORLAGE_OWNER", "PORTAL_REPO", "DEPLOY_HOST"):
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
    return [e for e in log if e.get("aktion") in ("repo create", "repo edit", "secret")
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


@pytest.mark.parametrize("variable", ["DEPLOY_SSH_KEY_FILE", "DEPLOY_KNOWN_HOSTS_FILE"])
def test_geheimnisdatei_fehlt_oder_leer(umgebung, tmp_path, variable):
    leer = tmp_path / "leer"
    leer.write_text("")
    for wert in ("", str(tmp_path / "gibt-es-nicht"), str(leer)):
        r = umgebung.starte("meine-noten", "js", **{variable: wert})
        assert r.returncode == 1
        assert variable in r.stderr
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

    # 4. Environment und Secrets
    assert any(e.get("aktion") == "api" and e["endpunkt"] == f"repos/{repo}/environments/test-vm" for e in log)
    secrets = {(s["name"], s["env"]) for s in zustand["secrets"]}
    assert secrets == {("DEPLOY_SSH_KEY", "test-vm"), ("DEPLOY_KNOWN_HOSTS", "test-vm"), ("DEPLOY_HOST", "test-vm")}

    # 5. Ruleset: 1 Freigabe, Pflicht-Check "check", keine Ausnahme
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


def test_geheimnisse_nirgends_sichtbar(umgebung):
    r = umgebung.starte("noten-uebersicht", "python")
    assert r.returncode == 0, r.stderr
    log_text = umgebung.log_pfad.read_text()
    for geheimnis in (GEHEIMER_SCHLUESSEL, GEHEIMER_HOST_EINTRAG):
        assert geheimnis not in r.stdout
        assert geheimnis not in r.stderr
        assert geheimnis not in log_text
    # Die Werte kamen über die Standardeingabe (Prüfsumme im Log), nie als Argument.
    secrets = [e for e in umgebung.log() if e.get("aktion") == "secret"]
    assert len(secrets) == 3
    assert all("--body" not in e["argv"] and "-b" not in e["argv"] for e in secrets)


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
