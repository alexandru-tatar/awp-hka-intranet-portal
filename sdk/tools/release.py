#!/usr/bin/env python3
"""Portal-SDK für Python und JavaScript freigeben (06 §10).

Baut die auslieferbaren Kopien nach `sdk/dist/python/platform_sdk/` und
`sdk/dist/javascript/platform_sdk/`:
Quellcode aus `sdk/<sprache>/platform_sdk/`, dazu das Design-Kit (`kit.css`, `kit.js`,
`icons.svg`, `fonts/`) für den Entwicklungsmodus und die Prüfsumme `SHA256`.
Trägt die Summen unter der Version aus `VERSION` in `sdk/sdk-releases.json` ein
(Schlüssel `python` und `javascript`; beide Sprachen haben dieselbe Version und dasselbe Verfahren).

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
LANGUAGES = ("python", "javascript")
RELEASES = SDK / "sdk-releases.json"


def src(language: str) -> Path:
    return SDK / language / "platform_sdk"


def dist(language: str) -> Path:
    return SDK / "dist" / language / "platform_sdk"


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


def build_language(language: str) -> str:
    """Kopie einer Sprache nach `sdk/dist/<sprache>/platform_sdk/` bauen und die Prüfsumme zurückgeben."""
    target = dist(language)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(src(language), target, ignore=shutil.ignore_patterns("__pycache__", "node_modules", SUM_FILE_NAME))
    copy_kit(target / "kit")
    digest = tree_hash(target)
    (target / SUM_FILE_NAME).write_text(digest + "\n", encoding="utf-8")
    return digest


def release(check_only: bool = False) -> dict[str, str]:
    version = (src("python") / "VERSION").read_text(encoding="utf-8").strip()
    if (src("javascript") / "VERSION").read_text(encoding="utf-8").strip() != version:
        raise SystemExit("Python- und JavaScript-SDK müssen dieselbe Version haben.")
    digests = {language: build_language(language) for language in LANGUAGES}

    releases = json.loads(RELEASES.read_text(encoding="utf-8")) if RELEASES.is_file() else {}
    entry = releases.get(version, {})
    current = all(entry.get(language) == digest for language, digest in digests.items())
    if check_only:
        if not current:
            raise SystemExit(f"sdk-releases.json passt nicht zu {version}: `make sdk-release` ausführen.")
        return digests
    if not current:
        # Reihenfolge der Schlüssel: Sprachen, dann assertion_versions und released
        releases[version] = {
            **digests,
            "assertion_versions": entry.get("assertion_versions", [1]),
            "released": dt.date.today().isoformat(),
        }
        RELEASES.write_text(json.dumps(releases, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return digests


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="nur prüfen, ob sdk-releases.json aktuell ist")
    args = ap.parse_args(argv)
    for language, digest in release(check_only=args.check).items():
        print(f"{dist(language).relative_to(PORTAL)}  {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
