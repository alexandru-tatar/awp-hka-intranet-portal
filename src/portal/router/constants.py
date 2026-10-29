"""Konstanten der Router-Schicht."""

from typing import Final

ETAG: Final = "ETag"
IF_NONE_MATCH: Final = "if-none-match"
CACHE_CONTROL: Final = "Cache-Control"
X_PORTAL_KIT: Final = "X-Portal-Kit"
NAV_MAX_AGE: Final = "private, max-age=60"
UNAUTHORIZED: Final = '{"type":"urn:hka:problem:unauthorized","status":401}'
