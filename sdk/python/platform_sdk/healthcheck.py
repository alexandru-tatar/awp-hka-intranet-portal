"""Gesundheitstest für den Container (`HEALTHCHECK`): nur Standardbibliothek, Ausgang 0 oder 1."""

from __future__ import annotations

import os
import sys
import urllib.request


def main() -> int:
    url = f"http://127.0.0.1:{os.environ.get('PORT', '8080')}/healthz"
    try:
        with urllib.request.urlopen(url, timeout=2) as response:  # feste lokale Adresse
            return 0 if response.status == 200 else 1
    except OSError:
        return 1


if __name__ == "__main__":
    sys.exit(main())
