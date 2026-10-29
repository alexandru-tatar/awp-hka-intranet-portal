"""Design-Kit: Kontrast-Gate (UI9), Build-Ausgabe und die Regel „kein Hex-Farbwert außerhalb von tokens.css"."""

import json

from conftest import ROOT

import contrast


def test_ui9_all_pairs_pass():
    tokens = contrast.parse_tokens((ROOT / "kit" / "css" / "tokens.css").read_text())
    pairs = json.loads((ROOT / "kit" / "pairs.json").read_text())["pairs"]
    _, errors = contrast.check(tokens, pairs)
    assert errors == []


def test_ui9_deck_footer_grey_fails():
    tokens = {"--deck-grey": "#9a9fa8", "--bg": "#ffffff"}
    _, errors = contrast.check(tokens, [{"fg": "--deck-grey", "bg": "--bg", "kind": "text"}])
    assert errors and "2.66" in errors[0]


def test_uncovered_token_fails():
    _, errors = contrast.check({"--new": "#000000", "--bg": "#ffffff"},
                               [{"fg": "--bg", "bg": "--bg", "kind": "decorative"}])
    assert errors == ["token --new has no contrast pair in pairs.json"]


def test_ratio_formula_matches_spec_table():
    # values from the 04 §5 matrix (neutral palette) — checks the formula, not today's tokens
    assert round(contrast.ratio("#1b1f24", "#ffffff"), 2) == 16.56
    assert round(contrast.ratio("#6b7480", "#f3f5f7"), 2) == 4.33


def test_build_writes_hashed_files(kit_dist):
    m = json.loads((kit_dist / "kit-manifest.json").read_text())
    for key in ("kit.css", "kit.js", "icons.svg"):
        assert (kit_dist / m[key]).exists()
    assert (kit_dist / m["kit.js"]).stat().st_size <= 1024


def test_no_hex_outside_root():
    """Stand-in for the stylelint rule (UI10): hex colours only in tokens.css."""
    import re
    for css in (ROOT / "kit" / "css").glob("*.css"):
        if css.name == "tokens.css":
            continue
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css.read_text()), css.name
