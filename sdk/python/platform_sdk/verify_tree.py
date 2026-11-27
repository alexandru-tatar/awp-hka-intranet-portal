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

# PF-103 steht hier und nicht in texts.json: Die Prüfung soll auch melden können, wenn i18n.py oder texts.json kaputt sind.
PF103 = {
    "de": "FEHLER PF-103  –  Portal-Bibliothek verändert\nWas tun: Änderungen in platform_sdk/ zurücknehmen oder `make sdk-update` ausführen.",
    "en": "ERROR PF-103  –  Portal library changed\nWhat to do: Undo changes in platform_sdk/ or run `make sdk-update`.",
}


def _language() -> str:
    """Sprache der Meldung wie ``i18n.env_language``, bei kaputtem ``i18n``-Modul Deutsch."""
    try:
        from .i18n import env_language

        return env_language()
    except Exception:  # noqa: BLE001 – genau der Fall, den die Prüfung melden soll
        return "de"


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
    print(PF103.get(_language(), PF103["de"]), file=sys.stderr)  # PORTAL_LANG=de|en (HKA-101)
    return 1


if __name__ == "__main__":
    sys.exit(main())
