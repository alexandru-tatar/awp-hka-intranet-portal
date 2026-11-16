#!/usr/bin/env python3
"""Design-Kit für das Keycloak-Login-Theme freigeben.

Baut die auslieferbare Kopie nach `sdk/dist/keycloak-theme/`:
`kit.css` und `fonts/` (mit Lizenz `OFL.txt`) aus dem Design-Kit, dazu `VERSION` (= `kit/VERSION`)
und die Prüfsumme `SHA256` (gleiches Verfahren wie `tools/keycloak_theme.py` im Gateway).

Das Login-Theme liegt im Repository des Security-Gateways (`keycloak/`). Es holt die Kopie mit
`make keycloak-theme-update THEME_DIST=…`; jedes Repository baut danach für sich.
"""

# Normalerweise läuft das Skript unter Linux (DevContainer, WSL2). Die Windows-Anpassungen
# (Sortierung in tree_hash, Zeilenenden über .gitattributes, Konsolen-Kodierung in main) sind eine
# bewusste Absicherung für den seltenen Fall, dass jemand das Skript direkt unter Windows aufruft.
# Nicht entfernen.

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import tempfile
from pathlib import Path

SDK = Path(__file__).resolve().parent.parent
PORTAL = SDK.parent
KIT = PORTAL / "kit"
DIST = SDK / "dist" / "keycloak-theme"
SUM_FILE_NAME = "SHA256"

sys.path.insert(0, str(KIT / "tools"))

import build  # noqa: E402


def tree_hash(root: Path) -> str:
    """SHA-256 über die sortierte Liste (relativer Pfad, Inhalt) aller Dateien außer `SHA256`.

    Sortiert wird nach den Pfadteilen als Text, mit Groß-/Kleinschreibung: so ist die Reihenfolge auf
    Linux, macOS und Windows gleich. Muss mit `tools/keycloak_theme.py` im Gateway übereinstimmen.
    """
    digest = hashlib.sha256()
    files = sorted(
        (p for p in root.rglob("*") if p.is_file() and p.name != SUM_FILE_NAME and "__pycache__" not in p.parts),
        key=lambda p: p.relative_to(root).parts,
    )
    for path in files:
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return "sha256:" + digest.hexdigest()


def release() -> str:
    """Kopie nach `sdk/dist/keycloak-theme/` bauen und die Prüfsumme zurückgeben."""
    if DIST.exists():
        shutil.rmtree(DIST)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "dist"
        manifest = build.build(out)
        DIST.mkdir(parents=True)
        shutil.copyfile(out / manifest["kit.css"], DIST / "kit.css")  # kit.css verweist relativ auf fonts/
        shutil.copytree(out / "fonts", DIST / "fonts")
    if not (DIST / "fonts" / "OFL.txt").is_file():
        raise SystemExit("fonts/OFL.txt fehlt: die Schriften dürfen nur mit Lizenztext weitergegeben werden.")
    (DIST / "VERSION").write_text((KIT / "VERSION").read_text(encoding="utf-8").strip() + "\n", encoding="utf-8")
    digest = tree_hash(DIST)
    (DIST / SUM_FILE_NAME).write_text(digest + "\n", encoding="utf-8")
    return digest


def main(argv: list[str] | None = None) -> int:
    # Umlaute in Meldungen auch auf Windows-Konsolen mit alter Codepage nicht scheitern lassen
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(errors="backslashreplace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.parse_args(argv)
    digest = release()
    version = (DIST / "VERSION").read_text(encoding="utf-8").strip()
    print(f"{DIST.relative_to(PORTAL)}  {version}  {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
