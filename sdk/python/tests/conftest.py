"""Fixtures für die SDK-Tests: Testschlüssel, Assertion-Fabrik und eine kleine App mit dem SDK."""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
from platform_sdk import Portal, User
from platform_sdk.config import Config
from platform_sdk.jwks import JwksCache

ISSUER = "https://portal.test/"
PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
KEYS = JwksCache.static({"test-key": PRIVATE_KEY.public_key()})
MANIFEST = {
    "slug": "noten",
    "name": "Noten-Übersicht",
    "category": "Studium",
    "menu": {"label": "Meine Noten", "icon": "grades"},
    "roles": ["student"],
    "adapters": ["noten:read"],
    "version": "1.0.0",
}


def make_token(**overrides) -> str:
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": ["noten", "portal", "adapters"],
        "sub": "student-test",
        "name": "Erika Musterfrau",
        "roles": ["student"],
        "v": 1,
        "iat": now,
        "exp": now + 60,
    }
    claims.update(overrides)
    return jwt.encode(claims, PRIVATE_KEY, algorithm="RS256", headers={"kid": "test-key"})


def make_portal(*, dev: bool = False) -> Portal:
    config = Config(
        env="test",
        slug="noten",
        base_path="",
        api_url="http://127.0.0.1:9",  # nicht erreichbar: layout() nimmt das Ersatz-Menü
        adapters_url=None,
        issuer=ISSUER,
        dev=dev,
        manifest=MANIFEST,
    )
    portal = Portal(config)
    portal.jwks = KEYS
    return portal


def make_app(portal: Portal) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    portal.install(app)
    router = portal.router()

    @router.get("/", response_class=HTMLResponse)
    async def home(user: User = Depends(portal.user)) -> str:
        return await portal.layout(title="Start", body="<h1>Start</h1>", current=portal.url("/"), user=user)

    @router.get("/nur-professor", dependencies=[Depends(portal.requires("professor"))])
    async def professor() -> dict:
        return {"ok": True}

    @router.get("/noten")
    async def noten(user: User = Depends(portal.user)) -> dict:
        result = await portal.adapters.noten.list_my_grades()
        return {"count": len(result.items)}

    app.include_router(router)
    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(make_app(make_portal()))


@pytest.fixture
def dev_client() -> TestClient:
    return TestClient(make_app(make_portal(dev=True)))
