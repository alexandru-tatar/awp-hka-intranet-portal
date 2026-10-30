"""Prüfsumme über `platform_sdk/` (06 §10), für schnelle Rückmeldung in `make lint`.

Maßgeblich ist die Prüfung in der Pipeline gegen `sdk-releases.json` im Portal-Repository.
Die erwartete Summe dieser Kopie steht in `platform_sdk/SHA256` (geschrieben von `make sdk-release`).

    python -m platform_sdk.verify_tree    prüfen (Fehler PF-103)
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SUM_FILE_NAME = "SHA256"
SKIP_DIRS = {"__pycache__", "node_modules"}


def tree_hash(root: Path = ROOT) -> str:
    """SHA-256 über die sortierte Liste (relativer Pfad, Inhalt) aller Dateien außer `SHA256`."""
    digest = hashlib.sha256()
    files = sorted(
        p
        for p in root.rglob("*")
        if p.is_file() and p.name != SUM_FILE_NAME and not SKIP_DIRS & set(p.relative_to(root).parts)
    )
    for path in files:
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return "sha256:" + digest.hexdigest()


def main() -> int:
    sum_file = ROOT / SUM_FILE_NAME
    expected = sum_file.read_text(encoding="utf-8").strip() if sum_file.is_file() else ""
    if tree_hash() == expected:
        return 0
    print(
        "FEHLER PF-103  –  Portal-Bibliothek verändert\n"
        "Was tun: Änderungen in platform_sdk/ zurücknehmen oder `make sdk-update` ausführen.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
