#!/usr/bin/env python3
"""Contrast gate for the design kit (04 §5).

Reads colour tokens (`--name: #hex`) from css/tokens.css and the pairs in
pairs.json, prints the matrix, and exits non-zero when a pair is below its
threshold or a colour token is not covered by any pair.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
THRESHOLDS = {"text": 4.5, "large-text": 3.0, "ui": 3.0, "decorative": None}
TOKEN_RE = re.compile(r"(--[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?)\b")


def parse_tokens(css: str) -> dict[str, str]:
    return {name: value.lower() for name, value in TOKEN_RE.findall(css)}


def _channel(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    r, g, b = (_channel(int(h[i : i + 2], 16) / 255) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(fg: str, bg: str) -> float:
    hi, lo = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def check(tokens: dict[str, str], pairs: list[dict]) -> tuple[list[tuple], list[str]]:
    rows, errors = [], []
    for p in pairs:
        fg, bg, kind = p["fg"], p["bg"], p["kind"]
        if kind not in THRESHOLDS:
            errors.append(f"unknown kind {kind!r} for {fg} on {bg}")
            continue
        missing = [t for t in (fg, bg) if t not in tokens]
        if missing:
            errors.append(f"unknown token(s) {', '.join(missing)}")
            continue
        r = ratio(tokens[fg], tokens[bg])
        need = THRESHOLDS[kind]
        ok = need is None or round(r, 2) >= need
        rows.append((fg, bg, r, kind, need, ok))
        if not ok:
            errors.append(f"{fg} on {bg}: {r:.2f} < {need} ({kind})")
    covered = {t for p in pairs for t in (p["fg"], p["bg"])}
    for name in sorted(set(tokens) - covered):
        errors.append(f"token {name} has no contrast pair in pairs.json")
    return rows, errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tokens", type=Path, default=KIT / "css" / "tokens.css")
    ap.add_argument("--pairs", type=Path, default=KIT / "pairs.json")
    ap.add_argument("--markdown", action="store_true", help="print the matrix as a Markdown table")
    args = ap.parse_args(argv)

    tokens = parse_tokens(args.tokens.read_text(encoding="utf-8"))
    pairs = json.loads(args.pairs.read_text(encoding="utf-8"))["pairs"]
    rows, errors = check(tokens, pairs)

    if args.markdown:
        print("| Foreground | Background | Ratio | Requirement | Result |")
        print("|---|---|---|---|---|")
    for fg, bg, r, kind, need, ok in rows:
        req = f"{kind} {need}" if need else kind
        res = "pass" if ok else "FAIL"
        if args.markdown:
            print(f"| `{fg}` | `{bg}` | {r:.2f} | {req} | {res} |")
        else:
            print(f"{fg:<14} on {bg:<12} {r:6.2f}  {req:<16} {res}")

    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
