"""Gemeinsame Fixtures: gebautes Kit, Kopie von ``dev/`` je Test, Test-Client und Hilfsfunktionen."""

import json
import shutil
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from loguru import logger

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "kit" / "tools"))

from portal.app import create_app  # noqa: E402

import build  # noqa: E402


@pytest.fixture(scope="session")
def kit_dist(tmp_path_factory) -> Path:
    """Das Design-Kit einmal pro Testlauf in einen temporären Ordner bauen.

    :param tmp_path_factory: pytest-Fabrik für temporäre Ordner
    :return: Ordner mit dem gebauten Kit (``kit-manifest.json``, CSS, JS, Icons, Schriften)
    """
    out = tmp_path_factory.mktemp("kit") / "dist"
    build.build(out)
    return out


@pytest.fixture
def env(tmp_path, kit_dist) -> Path:
    """Eigene Kopie von ``dev/`` je Test, damit Tests Manifeste frei ändern oder kaputt machen können.

    Die Pfade in ``gateway.dev.yml`` zeigen auf das Schema im Projekt und auf das gebaute Kit.

    :param tmp_path: pytest-Ordner für diesen Test
    :param kit_dist: Ordner mit dem gebauten Kit
    :return: Der kopierte Ordner ``dev``
    """
    d = tmp_path / "dev"
    shutil.copytree(ROOT / "dev", d)
    cfg = (d / "gateway.dev.yml").read_text(encoding="utf-8")
    cfg = cfg.replace("../schemas/manifest.schema.json", str(ROOT / "schemas" / "manifest.schema.json"))
    cfg = cfg.replace("../kit/dist", str(kit_dist))
    (d / "gateway.dev.yml").write_text(cfg, encoding="utf-8")
    return d


@pytest.fixture
def client(env) -> TestClient:
    """Test-Client für die Anwendung im Dev-Modus (Testpersonen-Login); Redirects werden nicht verfolgt.

    :param env: Kopie von ``dev/``
    :return: Der Client
    """
    return TestClient(create_app(env / "gateway.dev.yml"), follow_redirects=False)


def login(client: TestClient, user: str) -> TestClient:
    """Als Testperson anmelden; das Session-Cookie bleibt im Client.

    :param client: Test-Client
    :param user: ID der Testperson aus ``dev/users.yml``, z. B. ``alexandru``
    :return: Derselbe Client
    """
    r = client.post("/login", data={"user": user, "next": "/"})
    assert r.status_code == 303
    return client


def write_manifest(env: Path, manifest: dict, name: str | None = None) -> None:
    """Ein Manifest in den Manifest-Ordner der Testkopie schreiben.

    :param env: Kopie von ``dev/``
    :param manifest: Inhalt des Manifests
    :param name: Dateiname ohne Endung, sonst der ``slug``
    """
    (env / "manifests" / f"{name or manifest['slug']}.json").write_text(json.dumps(manifest), encoding="utf-8")


@pytest.fixture
def caplog(caplog):
    """loguru-Meldungen für caplog sichtbar machen."""
    handler_id = logger.add(caplog.handler, format="{message}", level=0)
    yield caplog
    logger.remove(handler_id)
