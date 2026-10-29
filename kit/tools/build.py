#!/usr/bin/env python3
"""Build the design kit (04 §11).

Concatenates and lightly minifies the CSS and JS, writes content-hashed files
`kit-<sha256[:12]>.css/js` and `icons-<sha256[:12]>.svg` into dist/, and a
`kit-manifest.json` mapping logical names to hashed names. The gateway reads
only the manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
CSS_ORDER = ["tokens.css", "fonts.css", "base.css", "layout.css", "components.css", "print.css"]
JS_MAX_BYTES = 1024


def minify_css(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    src = re.sub(r"\s+", " ", src)
    src = re.sub(r"\s*([{}:;,>])\s*", r"\1", src)
    return src.replace(";}", "}").strip() + "\n"


def minify_js(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    lines = (line.strip() for line in src.splitlines())
    return "\n".join(line for line in lines if line) + "\n"


def _hashed(prefix: str, ext: str, data: bytes) -> str:
    return f"{prefix}-{hashlib.sha256(data).hexdigest()[:12]}.{ext}"


def build(out: Path) -> dict[str, str]:
    css = "".join((KIT / "css" / name).read_text(encoding="utf-8") for name in CSS_ORDER)
    css_bytes = minify_css(css).encode()
    js_bytes = minify_js((KIT / "js" / "kit.js").read_text(encoding="utf-8")).encode()
    if len(js_bytes) > JS_MAX_BYTES:
        raise SystemExit(f"kit.js is {len(js_bytes)} bytes, limit {JS_MAX_BYTES}")
    icons_bytes = (KIT / "icons" / "icons.svg").read_bytes()

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    manifest = {
        "version": (KIT / "VERSION").read_text(encoding="utf-8").strip(),
        "kit.css": _hashed("kit", "css", css_bytes),
        "kit.js": _hashed("kit", "js", js_bytes),
        "icons.svg": _hashed("icons", "svg", icons_bytes),
    }
    (out / manifest["kit.css"]).write_bytes(css_bytes)
    (out / manifest["kit.js"]).write_bytes(js_bytes)
    (out / manifest["icons.svg"]).write_bytes(icons_bytes)
    fonts = KIT / "fonts"
    if fonts.is_dir():
        shutil.copytree(fonts, out / "fonts")
    (out / "kit-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=KIT / "dist")
    args = ap.parse_args(argv)
    manifest = build(args.out)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
