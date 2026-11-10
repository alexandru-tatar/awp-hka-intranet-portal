"""Gateway mode: public-key verification, no portal session, manifest decisions and CSRF."""
from dataclasses import replace
import json
import re
import time
import uuid

from cryptography.hazmat.primitives.asymmetric import rsa
import httpx
import jwt
from jwt.algorithms import RSAAlgorithm
import pytest
from fastapi.testclient import TestClient

from portal.app import create_app
from portal.core.config import GatewayConfig, load_config


@pytest.fixture
def integrated(env):
    key = rsa.generate_private_key(65537, 2048)
    jwk = {**json.loads(RSAAlgorithm.to_jwk(key.public_key())), 'kid': 'gateway', 'alg': 'RS256', 'use': 'sig'}
    gateway = GatewayConfig('http://localhost:18080/', 'http://gateway:8080/.well-known/jwks.json', 'http://localhost:18080')
    cfg = replace(load_config(env / 'gateway.dev.yml'), auth_mode='gateway', gateway=gateway,
                  dev_users_file=None, redis_url=None, oidc=None, assertion=None)
    secret = env / 'service-token'
    secret.write_text('t' * 43)
    calls = []
    def jwks(request):
        calls.append(request)
        assert str(request.url) == gateway.jwks_url
        return httpx.Response(200, json={'keys': [jwk]})
    public_keys = httpx.Client(transport=httpx.MockTransport(jwks))
    app = create_app(cfg, registry_token_file=secret, gateway_http_client=public_keys)
    def token(**overrides):
        now = int(time.time())
        payload = {'iss': gateway.issuer, 'aud': gateway.audience, 'sub': 'student-1', 'name': 'Test Student',
                   'roles': ['student'], 'iat': now, 'exp': now + 60, 'jti': str(uuid.uuid4()), 'v': 1,
                   'token_use': 'portal-ui', 'csrf': 'c' * 22, **overrides}
        return jwt.encode(payload, key, algorithm='RS256', headers={'kid': 'gateway'})
    with TestClient(app, follow_redirects=False) as client:
        yield client, app, token, calls
    public_keys.close()


def headers(token):
    return {'X-Portal-Assertion': token, 'Authorization': 'Bearer ' + 't' * 43}


def test_valid_identity_no_session_or_private_key_and_protected_assets(integrated):
    client, app, token, calls = integrated
    portal = app.state.portal
    assert portal.session_store is portal.session_service is portal.session_write_service is None
    assert portal.login_service is portal.keys is portal.assertion_service is portal.proxy is None
    response = client.get('/', headers=headers(token()))
    assert response.status_code == 200 and 'Test Student' in response.text
    assert 'set-cookie' not in response.headers
    assert client.get('/').status_code == 401
    assert client.get('/_portal/static/icons.svg').status_code == 401
    assert client.get('/_portal/static/icons.svg', headers=headers(token())).status_code == 200
    assert len(calls) == 1  # public keys cached, assertions not cached
    assert client.get('/readyz').status_code == 200


@pytest.mark.parametrize('overrides', [
    {'exp': int(time.time()) - 1}, {'aud': 'noten'}, {'iss': 'https://attacker.invalid/'},
    {'token_use': 'micro-app'}, {'roles': 'student'}, {'csrf': ''}, {'sub': ''}, {'v': 2},
])
def test_bad_assertions_rejected(integrated, overrides):
    client, _app, token, _calls = integrated
    assert client.get('/', headers=headers(token(**overrides))).status_code == 401
    assert client.post('/internal/apps/noten/authorize', headers=headers(token(**overrides))).status_code == 401


def test_malformed_and_tampered_assertions(integrated):
    client, _app, token, _calls = integrated
    for value in ('invalid', token() + 'tampered'):
        assert client.get('/', headers=headers(value)).status_code == 401


def test_authorize_existing_rules_and_failures(integrated):
    client, _app, token, _calls = integrated
    url = '/internal/apps/noten/authorize'
    result = client.post(url, headers=headers(token()))
    assert result.status_code == 200
    assert result.json() == {'slug': 'noten', 'allowed': True, 'adapters': ['noten:read']}
    denied = client.post(url, headers=headers(token(roles=['employee'])))
    assert denied.status_code == 403 and denied.json()['allowed'] is False
    assert client.post('/internal/apps/unbekannt/authorize', headers=headers(token())).status_code == 404
    assert client.post(url, headers={'X-Portal-Assertion': token()}).status_code == 401
    assert client.post(url, headers={'Authorization': 'Bearer ' + 't' * 43}).status_code == 401
    assert client.get('/apps/noten/', headers=headers(token())).status_code == 404
    assert client.get('/login', headers=headers(token())).status_code == 404


def test_csrf_and_admin_roles_remain_required(integrated):
    client, _app, token, _calls = integrated
    admin = {**headers(token(roles=['platform-admin'])), 'Origin': 'http://localhost:18080'}
    page = client.get('/_portal/admin', headers=admin)
    assert page.status_code == 200
    csrf = re.search(r'name="csrf" value="([^"]+)"', page.text)[1]
    assert csrf == 'c' * 22
    url = '/_portal/admin/apps/noten/roles'
    # Find the existing form action rather than assume a new administrative API.
    actions = re.findall(r'action="([^"]+)"', page.text)
    url = next(action for action in actions if 'noten' in action and 'roles' in action)
    assert client.post(url, headers=admin, data={'roles': 'student', 'csrf': 'wrong'}).status_code == 400
    assert client.post(url, headers={**headers(token()), 'Origin': 'http://localhost:18080'}, data={'roles': 'student', 'csrf': csrf}).status_code == 403
    assert client.post(url, headers=admin, data={'roles': 'student', 'csrf': csrf}).status_code == 303
    assert client.get('/_portal/admin', headers=headers(token())).status_code == 403


def test_app_navigation_contract_with_public_keys(integrated):
    client, _app, token, _calls = integrated
    app_token = token(aud=['noten', 'portal', 'adapters'], azp='noten', token_use=None)
    response = client.get('/nav', headers={'Authorization': 'Bearer ' + app_token})
    assert response.status_code == 200
    assert client.get('/', headers={'X-Portal-Assertion': app_token}).status_code == 401


def test_public_keys_fail_closed_and_duplicate_assertions(integrated, monkeypatch):
    client, app, token, _calls = integrated
    valid = token()
    assert client.get('/', headers=[('X-Portal-Assertion', valid), ('X-Portal-Assertion', valid)]).status_code == 401
    def fail(*args, **kwargs):
        raise httpx.ConnectError('keys unavailable')
    monkeypatch.setattr(app.state.gateway_verifier.http, 'stream', fail)
    assert client.get('/', headers=headers(valid)).status_code == 401


def test_cross_origin_admin_with_correct_csrf_is_rejected(integrated):
    client, _app, token, _calls = integrated
    admin = {**headers(token(roles=['platform-admin'])), 'Origin': 'https://evil.invalid'}
    assert client.post('/_portal/admin/apps/noten/roles', headers=admin,
                       data={'roles': 'student', 'csrf': 'c' * 22}).status_code == 403


def test_gateway_config_no_portal_session_requirements(env):
    path = env / 'gateway.dev.yml'
    content = path.read_text().replace('env: dev', 'env: prod')
    path.write_text(content + '\nauth_mode: gateway\ngateway:\n  issuer: https://gateway.test/\n  jwks_url: https://gateway.test/.well-known/jwks.json\n  public_url: https://gateway.test\n')
    cfg = load_config(path)
    assert cfg.auth_mode == 'gateway'
    with pytest.raises(ValueError, match='SERVICE_TOKEN_FILE'):
        create_app(cfg)
