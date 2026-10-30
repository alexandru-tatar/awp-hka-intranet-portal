"""Zwischenspeicher für die öffentlichen Schlüssel des Portals (06 §6)."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx
import jwt

log = logging.getLogger("platform_sdk")

FRESH_S = 300
UNKNOWN_REFETCH_S = 30
STALE_MAX_S = 3600


class JwksCache:
    def __init__(self, url: str | None, keys: dict[str, Any] | None = None) -> None:
        self._url = url
        self._keys: dict[str, Any] = dict(keys or {})
        self._fetched_at = time.time() if keys else 0.0
        self._last_unknown = float("-inf")
        self._last_warning = float("-inf")
        self._lock = asyncio.Lock()

    @classmethod
    def static(cls, keys: dict[str, Any]) -> JwksCache:
        """Feste Schlüssel ohne Abruf (für Tests)."""
        cache = cls(None, keys)
        cache._fetched_at = float("inf")
        return cache

    async def get(self, kid: str, now: float | None = None) -> Any:
        now = time.time() if now is None else now
        fresh = now - self._fetched_at < FRESH_S
        if kid in self._keys and fresh:
            return self._keys[kid]
        if kid not in self._keys and now - self._last_unknown >= UNKNOWN_REFETCH_S:
            self._last_unknown = now
            await self._refetch(now)
        elif kid in self._keys and not fresh:
            await self._refetch(now)
        if kid in self._keys and now - self._fetched_at < STALE_MAX_S:
            return self._keys[kid]
        raise KeyError(kid)

    async def _refetch(self, now: float) -> None:
        if self._url is None:
            return
        started = self._fetched_at
        async with self._lock:
            if self._fetched_at != started:  # ein anderer Aufruf hat schon geholt
                return
            try:
                async with httpx.AsyncClient(timeout=2) as client:
                    response = await client.get(self._url)
                    response.raise_for_status()
                jwk_set = jwt.PyJWKSet.from_dict(response.json())
                self._keys = {k.key_id: k.key for k in jwk_set.keys if k.key_id}
                self._fetched_at = time.time()
            except (httpx.HTTPError, ValueError, jwt.PyJWTError) as exc:
                if now - self._last_warning >= 60:
                    self._last_warning = now
                    log.warning("JWKS nicht abrufbar: %s", type(exc).__name__)
