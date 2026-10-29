"""Manifest-Prüfung (03 §3, REG4/REG5) und die dateibasierte Registry-Quelle."""

import copy
from pathlib import Path

import pytest

from conftest import ROOT, write_manifest
from portal.registry import ManifestDirectorySource, ManifestValidator, Registry

GOOD = {
    "slug": "noten",
    "name": "Meine Noten",
    "category": "Studium",
    "menu": {"label": "Meine Noten", "icon": "grades"},
    "roles": ["student"],
    "adapters": ["noten:read"],
    "version": "1.0.0",
}


@pytest.fixture
def validator() -> ManifestValidator:
    return ManifestValidator(ROOT / "schemas" / "manifest.schema.json",
                             ["student", "employee"], ["noten:read"])


def mutate(**changes) -> dict:
    m = copy.deepcopy(GOOD)
    for k, v in changes.items():
        if v is None:
            m.pop(k, None)
        else:
            m[k] = v
    return m


def test_good_manifest(validator):
    assert validator.problems(GOOD) == []


@pytest.mark.parametrize("manifest, pointer", [
    (mutate(extra=1), "/"),
    (mutate(roles=[]), "/roles"),
    (mutate(slug="Ab"), "/slug"),
    (mutate(slug="a_b"), "/slug"),
    (mutate(slug="a" * 32), "/slug"),
    (mutate(menu={"label": "x", "icon": "rocket"}), "/menu/icon"),
    (mutate(version="1.0"), "/version"),
    (mutate(category="Forschung"), "/category"),
    (mutate(claims=["phone"]), "/claims/0"),
    (mutate(name=None), "/"),
])
def test_reg4_schema_errors_with_pointer(validator, manifest, pointer):
    problems = validator.problems(manifest)
    assert problems and any(p.startswith(pointer + ":") for p in problems), problems


def test_reg4_reserved_slug(validator):
    assert validator.problems(mutate(slug="login")) == ["/slug: 'login' is reserved"]


def test_reg5_unknown_role_and_scope_named(validator):
    problems = validator.problems(mutate(roles=["student", "dean"], adapters=["mail:send"]))
    assert "/roles: unknown role 'dean'" in problems
    assert "/adapters: unknown adapter scope 'mail:send'" in problems


def test_icon_enum_matches_sprite():
    import json, re
    enum = json.loads((ROOT / "schemas" / "manifest.schema.json").read_text())["properties"]["menu"]["properties"]["icon"]["enum"]
    sprite = re.findall(r'<symbol id="i-([a-z-]+)"', (ROOT / "kit" / "icons" / "icons.svg").read_text())
    assert sorted(enum) == sorted(sprite)


def test_dev_manifests_are_valid():
    import yaml
    cfg = yaml.safe_load((ROOT / "dev" / "gateway.dev.yml").read_text())
    v = ManifestValidator(ROOT / "schemas" / "manifest.schema.json", cfg["role_vocabulary"], cfg["adapter_scopes"])
    import json
    for f in (ROOT / "dev" / "manifests").glob("*.json"):
        assert v.problems(json.loads(f.read_text())) == [], f.name


def test_invalid_and_duplicate_manifests_are_skipped(env: Path, validator, caplog):
    write_manifest(env, mutate(slug="kaputt", roles=[]))
    write_manifest(env, GOOD, name="zz-duplicate")
    v = ManifestValidator(ROOT / "schemas" / "manifest.schema.json",
                          ["student", "employee", "professor"], ["noten:read", "mail:send"])
    snap = Registry(ManifestDirectorySource(env / "manifests", v, env / "state.yml")).reload()
    assert "kaputt" not in snap.apps
    assert snap.apps["noten"].status == "healthy"
    assert snap.apps["raumbuchung"].status == "unhealthy"
    assert "duplicate slug 'noten'" in caplog.text
