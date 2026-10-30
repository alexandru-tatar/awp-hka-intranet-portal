#!/usr/bin/env python3
"""Portal-SDK für Python freigeben (06 §10).

Baut die auslieferbare Kopie nach `sdk/dist/python/platform_sdk/`:
Quellcode aus `sdk/python/platform_sdk/`, dazu das Design-Kit (`kit.css`, `kit.js`,
`icons.svg`, `fonts/`) für den Entwicklungsmodus und die Prüfsumme `SHA256`.
Trägt die Summe unter der Version aus `VERSION` in `sdk/sdk-releases.json` ein.

Starter holen die Kopie mit `make sdk-update`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
import tempfile
from pathlib import Path

SDK = Path(__file__).resolve().parent.parent
PORTAL = SDK.parent
SRC = SDK / "python" / "platform_sdk"
DIST = SDK / "dist" / "python" / "platform_sdk"
RELEASES = SDK / "sdk-releases.json"

sys.path.insert(0, str(PORTAL / "kit" / "tools"))
sys.path.insert(0, str(SDK / "python"))

import build  # noqa: E402
from platform_sdk.verify_tree import SUM_FILE_NAME, tree_hash  # noqa: E402


def copy_kit(target: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "dist"
        manifest = build.build(out)
        target.mkdir(parents=True)
        for logical in ("kit.css", "kit.js", "icons.svg"):
            shutil.copyfile(out / manifest[logical], target / logical)
        if (out / "fonts").is_dir():
            shutil.copytree(out / "fonts", target / "fonts")


def release(check_only: bool = False) -> str:
    version = (SRC / "VERSION").read_text(encoding="utf-8").strip()
    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(SRC, DIST, ignore=shutil.ignore_patterns("__pycache__", SUM_FILE_NAME))
    copy_kit(DIST / "kit")
    digest = tree_hash(DIST)
    (DIST / SUM_FILE_NAME).write_text(digest + "\n", encoding="utf-8")

    releases = json.loads(RELEASES.read_text(encoding="utf-8")) if RELEASES.is_file() else {}
    entry = releases.get(version, {})
    if check_only:
        if entry.get("python") != digest:
            raise SystemExit(f"sdk-releases.json passt nicht zu {version}: `make sdk-release` ausführen.")
        return digest
    if entry.get("python") != digest:
        entry = {"python": digest, "assertion_versions": [1], "released": dt.date.today().isoformat()}
        releases[version] = entry
        RELEASES.write_text(json.dumps(releases, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return digest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="nur prüfen, ob sdk-releases.json aktuell ist")
    args = ap.parse_args(argv)
    digest = release(check_only=args.check)
    print(f"{DIST.relative_to(PORTAL)}  {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
