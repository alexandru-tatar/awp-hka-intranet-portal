"""Einstellungen aus der Umgebung (06 §2)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

DEV_REFUSED = "Der Entwicklungsmodus darf nicht in Produktion laufen."


@dataclass(frozen=True)
class Config:
    env: str
    slug: str
    base_path: str
    api_url: str
    adapters_url: str | None
    issuer: str
    dev: bool
    manifest: dict

    @classmethod
    def from_env(cls, manifest_path: str = "manifest.json") -> Config:
        env = os.environ.get("PORTAL_ENV", "development")
        base_path = os.environ.get("PORTAL_BASE_PATH", "").rstrip("/")
        dev_requested = os.environ.get("PORTAL_DEV", "") not in ("", "0")
        if dev_requested and (env == "production" or base_path):
            raise RuntimeError(DEV_REFUSED)
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        return cls(
            env=env,
            slug=os.environ.get("PORTAL_SLUG") or manifest["slug"],
            base_path=base_path,
            api_url=os.environ.get("PORTAL_API_URL", "http://portal-api:8001").rstrip("/"),
            adapters_url=os.environ.get("PORTAL_ADAPTERS_URL") or (None if dev_requested else "http://portal-adapters:8002"),
            issuer=os.environ.get("PORTAL_ISSUER", "https://portal.hka.example/"),
            dev=dev_requested,
            manifest=manifest,
        )
