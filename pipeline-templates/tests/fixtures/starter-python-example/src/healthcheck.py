"""Gesundheitstest für den Container: nur Standardbibliothek, kein curl."""
import os
import sys
import urllib.request

try:
    with urllib.request.urlopen(f"http://127.0.0.1:{os.environ.get('PORT', '8080')}/healthz", timeout=2) as r:
        sys.exit(0 if r.status == 200 else 1)
except OSError:
    sys.exit(1)
