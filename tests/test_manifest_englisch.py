"""Englische Namen in den Manifesten (HKA-101): Pflicht bei neuer Registrierung, beim Laden bereits registrierter Apps nicht."""

import copy
import json

import pytest
from conftest import ROOT, login, write_manifest
from portal.registry import CATEGORIES, AppView, ManifestValidator

GOOD = {
    "slug": "pruefung", "name": "Prüfungen", "name_en": "Examinations", "category": "Studium",
    "menu": {"label": "Prüfungen", "label_en": "Exams", "icon": "grades"}, "roles": ["student"], "version": "1.0.0",
}


def without_english():
    manifest = copy.deepcopy(GOOD)
    del manifest["name_en"], manifest["menu"]["label_en"]
    return manifest


@pytest.fixture
def validator():
    return ManifestValidator(ROOT / "schemas" / "manifest.schema.json", ["student"], [])


def test_strict_requires_both_english_fields(validator):
    assert validator.problems(GOOD) == []
    assert validator.problems(without_english()) == [
        "/: 'name_en' is a required property", "/menu: 'label_en' is a required property"]


def test_lenient_accepts_missing_english_for_registered_apps(validator):
    assert validator.problems(without_english(), lenient=True) == []
    assert validator.missing_english(without_english()) == ["/name_en", "/menu/label_en"]
    assert validator.missing_english(GOOD) == []


def test_lenient_still_reports_every_other_problem(validator):
    broken = without_english()
    del broken["roles"]
    broken["slug"] = "Nope"
    problems = validator.problems(broken, lenient=True)
    assert any("roles" in p for p in problems) and any("/slug" in p for p in problems)
    assert not any("name_en" in p or "label_en" in p for p in problems)


@pytest.mark.parametrize("field, value", [("name_en", ""), ("name_en", "x" * 61), ("name_en", "a\nb")])
def test_english_name_limits(validator, field, value):
    assert validator.problems({**GOOD, field: value}) != []


def test_english_label_limits(validator):
    assert validator.problems({**GOOD, "menu": {**GOOD["menu"], "label_en": "x" * 41}}) != []


def test_app_view_shows_english_only_in_english():
    app = AppView.from_manifest(GOOD, status="healthy")
    assert (app.display_name("de"), app.display_label("de")) == ("Prüfungen", "Prüfungen")
    assert (app.display_name("en"), app.display_label("en")) == ("Examinations", "Exams")


def test_app_view_falls_back_to_german_for_old_manifests():
    app = AppView.from_manifest(without_english(), status="healthy")
    assert (app.display_name("en"), app.display_label("en")) == ("Prüfungen", "Prüfungen")


def test_every_category_has_a_heading_in_both_languages():
    import yaml
    for code in ("de", "en"):
        messages = yaml.safe_load((ROOT / "src" / "portal" / "locales" / f"messages.{code}.yml").read_text(encoding="utf-8"))
        assert all(f"category.{c}" in messages for c in CATEGORIES), code


def test_menu_in_english_with_english_names_and_headings(client, env):
    login(client, "alexandru")
    de = client.get("/nav").text
    en = client.get("/nav", headers={"Accept-Language": "en"}).text
    assert "Meine Noten" in de and "My grades" not in de and ">Studium<" in de
    assert "My grades" in en and "Meine Noten" not in en and ">Studies<" in en and "Timetable" in en


def test_home_cards_in_english(client):
    html = login(client, "alexandru").get("/", headers={"Accept-Language": "en"}).text
    assert "My grades" in html and "Studies" in html and "Meine Noten" not in html


def test_menu_order_follows_the_shown_label(client, env):
    for slug, de, en in (("zzz-app", "Aaa zuerst", "Zzz last"), ("mmm-app", "Mmm mitte", "Mmm middle")):
        write_manifest(env, {**GOOD, "slug": slug, "name": de, "name_en": en,
                             "menu": {"label": de, "label_en": en, "icon": "info"}})
    state = env / "state.yml"
    state.write_text(state.read_text() + "\nzzz-app: healthy\nmmm-app: healthy\n")
    login(client, "alexandru")
    de = client.get("/nav").text
    en = client.get("/nav", headers={"Accept-Language": "en"}).text
    assert de.index("Aaa zuerst") < de.index("Mmm mitte")
    assert en.index("Mmm middle") < en.index("Zzz last")


def test_old_manifest_without_english_still_appears_in_the_menu(client, env):
    manifest = {**without_english(), "slug": "altapp", "name": "Alte App", "menu": {"label": "Alte App", "icon": "info"}}
    write_manifest(env, manifest)
    (env / "state.yml").write_text((env / "state.yml").read_text() + "\naltapp: healthy\n")
    login(client, "alexandru")
    assert "Alte App" in client.get("/nav", headers={"Accept-Language": "en"}).text
