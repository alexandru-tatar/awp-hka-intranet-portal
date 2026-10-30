"""Angemeldete Person und Kontext der laufenden Anfrage (06 §3.1, §8)."""

from __future__ import annotations

import hashlib
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    sub: str
    name: str
    roles: tuple[str, ...]
    email: str | None = None

    @property
    def hash(self) -> str:
        """Erste 12 Hex-Zeichen von SHA-256(sub), nur zur Zuordnung im Log (06 §11)."""
        return hashlib.sha256(self.sub.encode()).hexdigest()[:12]


current_user: ContextVar[User | None] = ContextVar("portal_user", default=None)
current_assertion: ContextVar[str | None] = ContextVar("portal_assertion", default=None)
current_request_id: ContextVar[str | None] = ContextVar("portal_request_id", default=None)
