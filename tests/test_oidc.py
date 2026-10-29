"""OIDC-Anmeldung gegen einen gefälschten IdP, Sessions in fakeredis (02 §4, §5; G2/G4/G6)."""

import time
from urllib.parse import parse_qs, urlparse

import fakeredis
import httpx
import jwt
from redis.exceptions import RedisError
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm

from conftest import ROOT
from portal.app import create_app
from portal.auth.redis_sessions import RedisSessionStore

ISSUER = "https://idp.test/realms/hka"
CLIENT_ID = "portal"
KID = "test-key"


class FakeIdp:
    """Discovery, JWKS and token endpoint; issues whatever `claims`/`overrides` say."""

    def __init__(self) -> None:
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.nonce: str | None = None
        self.claims: dict = {"sub": "u-1", "name": "Alexandru Tatar", "eduPersonAffiliation": ["student"]}
        self.overrides: dict = {}
        self.token_status = 200
        self.codes_used = 0
        self.end_session = True

    def handle(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/.well-known/openid-configuration"):
            document = {
                "issuer": ISSUER,
                "authorization_endpoint": f"{ISSUER}/auth",
                "token_endpoint": f"{ISSUER}/token",
                "jwks_uri": f"{ISSUER}/certs",
            }
            if self.end_session:
                document["end_session_endpoint"] = f"{ISSUER}/logout"
            return httpx.Response(200, json=document)
        if url.endswith("/certs"):
            jwk = RSAAlgorithm.to_jwk(self.key.public_key(), as_dict=True)
            return httpx.Response(200, json={"keys": [{**jwk, "kid": KID, "alg": "RS256", "use": "sig"}]})
        if url.endswith("/token"):
            self.codes_used += 1
            if self.token_status != 200:
                return httpx.Response(self.token_status)
            return httpx.Response(200, json={"id_token": self.id_token()})
        return httpx.Response(404)

    def id_token(self, **extra) -> str:
        now = int(time.time())
        claims = {"iss": ISSUER, "aud": CLIENT_ID, "iat": now, "exp": now + 300, "nonce": self.nonce,
                  **self.claims, **self.overrides, **extra}
        claims = {k: v for k, v in claims.items() if v is not None}
        return jwt.encode(claims, self.key, algorithm="RS256", headers={"kid": KID})


@pytest.fixture
def idp() -> FakeIdp:
    return FakeIdp()


@pytest.fixture
def redis_client():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def oidc_config(env):
    cfg = (ROOT / "dev" / "gateway.oidc.yml").read_text(encoding="utf-8")
    cfg = cfg.replace("../schemas/manifest.schema.json", str(ROOT / "schemas" / "manifest.schema.json"))
    cfg = cfg.replace("http://localhost:8180/realms/hka", ISSUER)
    cfg = cfg.replace("http://localhost:8000/oidc/callback", "http://testserver/oidc/callback")
    cfg = cfg.replace("post_logout_redirect_uri: http://localhost:8000/", "post_logout_redirect_uri: http://testserver/")
    cfg = cfg.replace("redis://localhost:6379/0", "redis://fake:6379/0")
    return cfg, env


@pytest.fixture
def client(oidc_config, kit_dist, idp, redis_client):
    cfg, env = oidc_config
    cfg = cfg.replace("../kit/dist", str(kit_dist))
    (env / "gateway.oidc.yml").write_text(cfg, encoding="utf-8")
    app = create_app(
        env / "gateway.oidc.yml",
        redis_client=redis_client,
        http_client=httpx.Client(transport=httpx.MockTransport(idp.handle)),
    )
    return TestClient(app, follow_redirects=False)


def start_login(client, idp, next_path="/"):
    r = client.get("/login", params={"next": next_path})
    assert r.status_code == 302
    query = parse_qs(urlparse(r.headers["location"]).query)
    idp.nonce = query["nonce"][0]
    return r, query


def finish_login(client, idp, query, **params):
    return client.get("/oidc/callback", params={"code": "c", "state": query["state"][0], **params})


def test_login_redirects_to_idp_with_pkce_and_sets_login_cookie(client, idp):
    r, query = start_login(client, idp)
    assert r.headers["location"].startswith(f"{ISSUER}/auth?")
    assert query["code_challenge_method"] == ["S256"] and query["response_type"] == ["code"]
    assert query["client_id"] == [CLIENT_ID] and "openid" in query["scope"][0]
    assert "portal_login" in client.cookies
    assert "httponly" in r.headers["set-cookie"].lower()


def test_full_login_creates_session_with_mapped_roles(client, idp, redis_client):
    _, query = start_login(client, idp)
    r = finish_login(client, idp, query)
    assert r.status_code == 302 and r.headers["location"] == "/"
    assert "portal_sid" in client.cookies and "portal_login" not in client.cookies
    sid = client.cookies["portal_sid"]
    assert redis_client.hget(f"sess:{sid}", "roles") == '["student"]'
    assert 0 < redis_client.ttl(f"sess:{sid}") <= 1800
    home = client.get("/")
    assert home.status_code == 200 and "Alexandru Tatar" in home.text


def test_next_is_kept_and_sanitized(client, idp):
    _, query = start_login(client, idp, "/apps/noten/")
    assert finish_login(client, idp, query).headers["location"] == "/apps/noten/"


def test_next_open_redirect_is_replaced(client, idp):
    _, query = start_login(client, idp, "//evil.example/")
    assert finish_login(client, idp, query).headers["location"] == "/"


def test_g2_callback_without_login_cookie_is_400_and_creates_no_session(client, idp, redis_client):
    _, query = start_login(client, idp)
    client.cookies.delete("portal_login")
    r = finish_login(client, idp, query)
    assert r.status_code == 400
    assert not redis_client.keys("sess:*")
    assert idp.codes_used == 0


def test_g4_replayed_callback_fails(client, idp, redis_client):
    _, query = start_login(client, idp)
    lid = client.cookies["portal_login"]
    assert finish_login(client, idp, query).status_code == 302
    client.cookies.set("portal_login", lid)
    assert finish_login(client, idp, query).status_code == 400
    assert len(redis_client.keys("sess:*")) == 1


def test_g6_new_session_id_differs_and_old_one_is_deleted(client, idp, redis_client):
    old = client.cookies  # nothing yet
    _, query = start_login(client, idp)
    finish_login(client, idp, query)
    first = client.cookies["portal_sid"]
    _, query = start_login(client, idp)
    finish_login(client, idp, query)
    second = client.cookies["portal_sid"]
    assert first != second
    assert not redis_client.exists(f"sess:{first}") and redis_client.exists(f"sess:{second}")


def test_state_mismatch_is_400(client, idp):
    _, query = start_login(client, idp)
    assert client.get("/oidc/callback", params={"code": "c", "state": "falsch"}).status_code == 400


def test_idp_error_is_400_without_details(client, idp):
    _, query = start_login(client, idp)
    r = client.get("/oidc/callback", params={"error": "access_denied", "state": query["state"][0]})
    assert r.status_code == 400 and "access_denied" not in r.text


@pytest.mark.parametrize("overrides", [
    {"nonce": "anderer"},
    {"aud": "fremd"},
    {"iss": "https://evil.test"},
    {"exp": 1},
    {"sub": ""},
], ids=["nonce", "aud", "iss", "expired", "empty-sub"])
def test_invalid_id_token_is_rejected(client, idp, redis_client, overrides):
    idp.overrides = overrides
    _, query = start_login(client, idp)
    assert finish_login(client, idp, query).status_code == 400
    assert not redis_client.keys("sess:*")


@pytest.mark.parametrize("make_token", [
    lambda idp: jwt.encode({"iss": ISSUER, "aud": CLIENT_ID, "sub": "x", "iat": int(time.time()),
                            "exp": int(time.time()) + 60, "nonce": idp.nonce}, None, algorithm="none"),
    lambda idp: jwt.encode({"iss": ISSUER, "aud": CLIENT_ID, "sub": "x", "iat": int(time.time()),
                            "exp": int(time.time()) + 60, "nonce": idp.nonce}, "k" * 32, algorithm="HS256"),
], ids=["alg-none", "alg-hmac"])
def test_unsigned_and_hmac_tokens_are_rejected(client, idp, make_token):
    idp.id_token = lambda **_: make_token(idp)
    _, query = start_login(client, idp)
    assert finish_login(client, idp, query).status_code == 400


def test_token_endpoint_failure_is_400(client, idp):
    idp.token_status = 401
    _, query = start_login(client, idp)
    assert finish_login(client, idp, query).status_code == 400


def test_unmapped_claims_give_no_roles_and_empty_menu(client, idp, redis_client):
    idp.claims = {"sub": "u-2", "name": "Niemand", "eduPersonAffiliation": ["alumni"]}
    _, query = start_login(client, idp)
    finish_login(client, idp, query)
    sid = client.cookies["portal_sid"]
    assert redis_client.hget(f"sess:{sid}", "roles") == "[]"


def test_entitlement_maps_to_platform_admin(client, idp):
    idp.claims = {"sub": "u-3", "name": "Sam", "eduPersonAffiliation": ["employee"],
                  "eduPersonEntitlement": ["urn:hka:portal:admin"]}
    _, query = start_login(client, idp)
    finish_login(client, idp, query)
    assert client.get("/_portal/status").status_code == 200


def test_logout_removes_session_from_redis(client, idp, redis_client):
    _, query = start_login(client, idp)
    finish_login(client, idp, query)
    sid = client.cookies["portal_sid"]
    csrf = redis_client.hget(f"sess:{sid}", "csrf")
    assert client.post("/logout", data={"csrf": csrf}).status_code == 303
    assert not redis_client.exists(f"sess:{sid}")
    assert not redis_client.keys("usr:*") or all(not redis_client.smembers(k) for k in redis_client.keys("usr:*"))


def test_logout_redirects_to_idp_end_session_with_id_token_hint(client, idp, redis_client):
    _, query = start_login(client, idp)
    finish_login(client, idp, query)
    sid = client.cookies["portal_sid"]
    csrf = redis_client.hget(f"sess:{sid}", "csrf")
    stored = redis_client.hget(f"sess:{sid}", "id_token")
    assert stored
    r = client.post("/logout", data={"csrf": csrf})
    location = urlparse(r.headers["location"])
    params = parse_qs(location.query)
    assert r.status_code == 303 and f"{location.scheme}://{location.netloc}{location.path}" == f"{ISSUER}/logout"
    assert params["id_token_hint"] == [stored] and params["client_id"] == [CLIENT_ID]
    assert params["post_logout_redirect_uri"] == ["http://testserver/"]


def test_logout_drops_id_token_hint_after_idp_key_change(client, idp, redis_client):
    """IdP neu gestartet bzw. Schlüssel gewechselt: der alte ID-Token-Hint würde beim IdP „Ungültiger Parameter" auslösen."""
    _, query = start_login(client, idp)
    finish_login(client, idp, query)
    sid = client.cookies["portal_sid"]
    csrf = redis_client.hget(f"sess:{sid}", "csrf")
    idp.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)  # neue Schlüssel, gleiche kid
    r = client.post("/logout", data={"csrf": csrf})
    params = parse_qs(urlparse(r.headers["location"]).query)
    assert r.status_code == 303 and "id_token_hint" not in params
    assert params["client_id"] == [CLIENT_ID] and params["post_logout_redirect_uri"] == ["http://testserver/"]


def test_logout_keeps_hint_when_token_is_expired_but_signature_is_current(client, idp, redis_client):
    _, query = start_login(client, idp)
    finish_login(client, idp, query)
    sid = client.cookies["portal_sid"]
    csrf = redis_client.hget(f"sess:{sid}", "csrf")
    redis_client.hset(f"sess:{sid}", "id_token", idp.id_token(exp=1, iat=1))
    params = parse_qs(urlparse(client.post("/logout", data={"csrf": csrf}).headers["location"]).query)
    assert "id_token_hint" in params


def test_logout_without_end_session_endpoint_goes_home(client, idp):
    idp.end_session = False
    _, query = start_login(client, idp)
    finish_login(client, idp, query)
    sid = client.cookies["portal_sid"]
    csrf = client.app.state.portal.session_store.get(sid).csrf
    r = client.post("/logout", data={"csrf": csrf})
    assert r.status_code == 303 and r.headers["location"] == "/"


def test_dev_login_picker_is_not_mounted_in_oidc_mode(client):
    r = client.post("/login", data={"user": "alexandru"})
    assert r.status_code == 405


def test_readyz_ok_and_503_when_redis_down(client, redis_client, monkeypatch):
    assert client.get("/readyz").status_code == 200
    monkeypatch.setattr(redis_client, "ping", lambda: (_ for _ in ()).throw(RedisError("down")))
    r = client.get("/readyz")
    assert r.status_code == 503 and r.json()["check"] == "redis"


def test_redis_down_fails_closed_with_503_page(client, idp, redis_client, monkeypatch):
    _, query = start_login(client, idp)
    finish_login(client, idp, query)
    monkeypatch.setattr(redis_client, "hgetall", lambda *_: (_ for _ in ()).throw(RedisError("down")))
    assert client.get("/").status_code == 503


class TestRedisSessionStore:
    def make(self, redis_client, **kw):
        return RedisSessionStore(redis_client, idle_seconds=1800, absolute_seconds=100,
                                 touch_min_interval_seconds=60, **kw)

    def test_absolute_lifetime_ends_session(self, redis_client):
        store = self.make(redis_client)
        s = store.create("sub", "Name", frozenset({"student"}))
        assert store.get(s.sid) is not None
        redis_client.hset(f"sess:{s.sid}", "created", int(time.time()) - 101)
        assert store.get(s.sid) is None
        assert not redis_client.exists(f"sess:{s.sid}")

    def test_touch_writes_at_most_once_per_interval(self, redis_client):
        store = self.make(redis_client)
        s = store.create("sub", "Name", frozenset())
        before = redis_client.hget(f"sess:{s.sid}", "last_seen")
        for _ in range(50):
            store.get(s.sid)
        assert redis_client.hget(f"sess:{s.sid}", "last_seen") == before
        redis_client.hset(f"sess:{s.sid}", "last_seen", int(time.time()) - 61)
        store.get(s.sid)
        assert int(redis_client.hget(f"sess:{s.sid}", "last_seen")) >= int(time.time()) - 1

    def test_unknown_and_empty_sid(self, redis_client):
        store = self.make(redis_client)
        assert store.get("gibt-es-nicht") is None and store.get(None) is None
