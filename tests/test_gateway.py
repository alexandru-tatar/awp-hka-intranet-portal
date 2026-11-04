"""Weiterleitung an App-Container und Identitäts-Token (HKA-52, AK1 bis AK6)."""

import json
import time

import httpx
import jwt
import pytest
from conftest import login
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm

from portal.app import create_app
from portal.auth.assertion_keys import InvalidAssertion, thumbprint
from portal.core.config import ConfigError, load_config

ISSUER = "http://portal.test/"


class FakeApps:
    """Ersatz für die App-Container: protokolliert Anfragen, antwortet je nach Pfad."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.fail: Exception | None = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fail is not None:
            raise self.fail
        if request.url.path.endswith("/moved"):
            return httpx.Response(302, headers={"Location": "http://app-noten:8080/apps/noten/ziel"})
        return httpx.Response(
            200,
            content=b"hallo",
            headers={"Content-Type": "text/plain", "Set-Cookie": "x=1", "Cache-Control": "private"},
        )


@pytest.fixture
def apps() -> FakeApps:
    return FakeApps()


@pytest.fixture
def gateway_cfg(env):
    """Konfiguration mit ``assertion`` und ``apps`` (flüchtiger Schlüssel, da env dev)."""
    path = env / "gateway.dev.yml"
    path.write_text(
        path.read_text(encoding="utf-8")
        + f"\nassertion:\n  issuer: {ISSUER}\napps:\n  upstream: http://app-{{slug}}:8080\n  max_body_bytes: 100\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def gw(gateway_cfg, apps) -> TestClient:
    app = create_app(gateway_cfg, app_transport=httpx.MockTransport(apps))
    return TestClient(app, follow_redirects=False)


def token_of(apps: FakeApps) -> str:
    return apps.requests[-1].headers["x-portal-assertion"]


def decode(client: TestClient, token: str, audience: str) -> dict:
    keys = client.get("/.well-known/jwks.json").json()["keys"]
    header = jwt.get_unverified_header(token)
    jwk = next(k for k in keys if k["kid"] == header["kid"])
    return jwt.decode(token, RSAAlgorithm.from_jwk(json.dumps(jwk)), algorithms=["RS256"], audience=audience, issuer=ISSUER)


def test_ak1_forwards_path_query_and_body(gw, apps):
    login(gw, "alexandru")
    r = gw.get("/apps/noten/x/y?a=1")
    assert r.status_code == 200 and r.text == "hallo"
    req = apps.requests[-1]
    assert str(req.url) == "http://app-noten:8080/apps/noten/x/y?a=1"
    r = gw.post("/apps/noten/", content=b"abc")
    assert r.status_code == 200 and apps.requests[-1].content == b"abc"
    assert gw.get("/apps/noten").status_code == 308


def test_ak1_no_cookies_to_app_and_none_back(gw, apps):
    login(gw, "alexandru")
    r = gw.get("/apps/noten/")
    assert "cookie" not in apps.requests[-1].headers
    assert "set-cookie" not in r.headers
    assert r.headers["cache-control"] == "private"


def test_location_of_app_is_made_relative(gw, apps):
    login(gw, "alexandru")
    r = gw.get("/apps/noten/moved")
    assert r.status_code == 302 and r.headers["location"] == "/apps/noten/ziel"


def test_ak2_token_claims(gw, apps):
    login(gw, "alexandru")
    gw.get("/apps/noten/")
    token = token_of(apps)
    claims = decode(gw, token, "noten")
    assert claims["iss"] == ISSUER and claims["v"] == 1
    assert claims["aud"] == ["noten", "portal", "adapters"]
    assert claims["sub"] == "dev:alexandru" and claims["name"] == "Alexandru Tatar"
    assert claims["roles"] == ["student"] and claims["azp"] == "noten" and claims["scp"] == ["noten:read"]
    assert claims["exp"] - claims["iat"] == 60 and claims["jti"]
    assert "email" not in claims
    header = jwt.get_unverified_header(token)
    assert header["alg"] == "RS256" and header["typ"] == "JWT"


def test_ak3_jwks_has_kid_and_cache_header(gw, apps):
    login(gw, "alexandru")
    gw.get("/apps/noten/")
    r = gw.get("/.well-known/jwks.json")
    assert r.status_code == 200 and r.headers["cache-control"] == "public, max-age=300"
    keys = r.json()["keys"]
    assert jwt.get_unverified_header(token_of(apps))["kid"] in {k["kid"] for k in keys}
    jwk = keys[0]
    assert jwk["kty"] == "RSA" and jwk["alg"] == "RS256" and jwk["use"] == "sig"
    assert jwk["kid"] == thumbprint(RSAAlgorithm.from_jwk(json.dumps(jwk)))


def test_jwks_missing_without_assertion_section(client):
    assert client.get("/.well-known/jwks.json").status_code == 404


def test_ak4_refused_requests_never_reach_app(gw, apps):
    assert gw.get("/apps/noten/").headers["location"] == "/login?next=/apps/noten/"
    login(gw, "gast")
    assert gw.get("/apps/noten/").status_code == 403
    assert gw.get("/apps/gibtsnicht/").status_code == 404
    assert apps.requests == []


def test_ak5_forged_assertion_is_replaced(gw, apps):
    login(gw, "alexandru")
    gw.get("/apps/noten/", headers={"X-Portal-Assertion": "gefaelscht", "x-portal-assertion": "noch-einer"})
    sent = apps.requests[-1].headers.get_list("x-portal-assertion")
    assert len(sent) == 1 and sent[0] != "gefaelscht" and sent[0].count(".") == 2


def test_ak5_token_for_other_app_is_rejected_by_audience(gw, apps):
    login(gw, "alexandru")
    gw.get("/apps/noten/")
    with pytest.raises(jwt.InvalidAudienceError):
        decode(gw, token_of(apps), "stundenplan")


def test_ak6_unhealthy_app_gives_503_without_request(gw, apps):
    login(gw, "max")
    assert gw.get("/apps/raumbuchung/").status_code == 503
    assert apps.requests == []


def test_ak6_unreachable_container_gives_503_page(gw, apps):
    login(gw, "alexandru")
    apps.fail = httpx.ConnectError("down")
    r = gw.get("/apps/noten/")
    assert r.status_code == 503 and "text/html" in r.headers["content-type"]


def test_timeout_gives_504_and_other_error_502(gw, apps):
    login(gw, "alexandru")
    apps.fail = httpx.ReadTimeout("slow")
    assert gw.get("/apps/noten/").status_code == 504
    apps.fail = httpx.RemoteProtocolError("kaputt")
    assert gw.get("/apps/noten/").status_code == 502


def test_csrf_cross_site_post_is_refused(gw, apps):
    login(gw, "alexandru")
    n = len(apps.requests)
    assert gw.post("/apps/noten/", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert gw.post("/apps/noten/", headers={"Origin": "http://evil.example"}).status_code == 403
    assert len(apps.requests) == n
    assert gw.post("/apps/noten/", headers={"Sec-Fetch-Site": "same-origin"}).status_code == 200
    assert gw.get("/apps/noten/", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 200


def test_body_over_limit_gives_413(gw, apps):
    login(gw, "alexandru")
    assert gw.post("/apps/noten/", content=b"x" * 101).status_code == 413
    assert apps.requests == []


def test_token_is_not_logged(gw, apps, caplog):
    login(gw, "alexandru")
    gw.get("/apps/noten/")
    assert token_of(apps) not in caplog.text


def test_prod_without_key_is_a_config_error(gateway_cfg):
    gateway_cfg.write_text(gateway_cfg.read_text(encoding="utf-8").replace("env: dev", "env: prod", 1), encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(gateway_cfg)


def test_key_from_file_is_used_and_next_previous_are_published(gateway_cfg, env):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    kids = []
    for name in ("current", "next", "previous"):
        key = rsa.generate_private_key(65537, 2048)
        (env / f"{name}.pem").write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
            )
        )
        kids.append(thumbprint(key.public_key()))
    gateway_cfg.write_text(
        gateway_cfg.read_text(encoding="utf-8").replace(
            f"issuer: {ISSUER}",
            f"issuer: {ISSUER}\n  signing_key_current: current.pem\n  signing_key_next: next.pem\n  signing_key_previous: previous.pem",
            1,
        ),
        encoding="utf-8",
    )
    app = create_app(gateway_cfg)
    portal = app.state.portal
    assert portal.keys.current.kid == kids[0]
    assert [k["kid"] for k in portal.keys.jwks()["keys"]] == kids


def test_verify_rejects_foreign_tokens(gw):
    keys = gw.app.state.portal.keys
    now = int(time.time())
    good = {"iss": ISSUER, "sub": "a", "roles": [], "aud": ["portal"], "iat": now, "exp": now + 60, "v": 1}
    assert keys.verify(keys.sign(good), "portal")["sub"] == "a"
    for bad in ({**good, "aud": ["noten"]}, {**good, "iss": "x"}, {**good, "v": 2}, {**good, "exp": now - 60}):
        with pytest.raises(InvalidAssertion):
            keys.verify(keys.sign(bad), "portal")
    with pytest.raises(InvalidAssertion):
        keys.verify("kein.token.hier", "portal")


NAV_TOKEN_HEADERS = {
    "bearer": lambda t: {"Authorization": f"Bearer {t}"},  # 02 §3, SDK ab 1.0.1-dev
    "bearer-kleingeschrieben": lambda t: {"Authorization": f"bearer {t}"},
    "x-portal-assertion": lambda t: {"X-Portal-Assertion": t},  # Übergang für SDK bis 1.0.0-dev
}


@pytest.mark.parametrize("form", NAV_TOKEN_HEADERS)
def test_nav_accepts_assertion_with_portal_audience(gw, apps, form):
    login(gw, "alexandru")
    gw.get("/apps/noten/")
    token = token_of(apps)
    gw.cookies.clear()
    r = gw.get("/nav", headers=NAV_TOKEN_HEADERS[form](token))
    assert r.status_code == 200 and "Meine Noten" in r.text and "x-portal-kit" in r.headers
    assert "Raumbuchung" not in r.text


@pytest.mark.parametrize("form", NAV_TOKEN_HEADERS)
def test_nav_rejects_bad_assertion(gw, form):
    keys = gw.app.state.portal.keys
    now = int(time.time())
    claims = {"iss": ISSUER, "sub": "a", "roles": ["student"], "iat": now, "exp": now + 60, "v": 1}
    wrong_aud = keys.sign({**claims, "aud": ["noten"]})
    forged = wrong_aud[:-4] + "AAAA"
    for token in (wrong_aud, "x.y.z", forged):
        assert gw.get("/nav", headers=NAV_TOKEN_HEADERS[form](token)).status_code == 401


def test_nav_bearer_wins_over_transition_header(gw):
    keys = gw.app.state.portal.keys
    now = int(time.time())
    claims = {"iss": ISSUER, "sub": "a", "roles": ["student"], "iat": now, "exp": now + 60, "v": 1}
    good = keys.sign({**claims, "aud": ["portal"]})
    r = gw.get("/nav", headers={"Authorization": f"Bearer {good}", "X-Portal-Assertion": "x.y.z"})
    assert r.status_code == 200


def test_nav_other_auth_scheme_without_session_is_401(gw):
    assert gw.get("/nav", headers={"Authorization": "Basic YTpi"}).status_code == 401


def test_kit_files_are_served_under_sdk_names(client):
    kit = client.app.state.portal.kit
    for alias, real in kit.aliases.items():
        r = client.get(f"/_portal/static/{alias}")
        assert r.status_code == 200 and r.headers["cache-control"] == "no-cache"
        assert r.content == client.get(f"/_portal/static/{real}").content
    assert client.get(kit.css_url).headers["cache-control"].endswith("immutable")
