"""Real portal + standalone gateway + supplied SyncShare SDK app, in-process only."""
from dataclasses import replace
import importlib
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import fakeredis
from fastapi.testclient import TestClient
import httpx
import jwt
import pytest

from portal.app import create_app as create_portal
from portal.core.config import GatewayConfig, load_config

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'awp-hka-security-gateway' / 'src'))
pytest.importorskip('gateway.app', reason='Sibling gateway required for cross-project flow test')
from gateway.app import create_app as create_gateway  # noqa: E402
from gateway.config import Settings, OidcConfig, AppsConfig  # noqa: E402
from gateway.registry_client import RegistryClient  # noqa: E402


def test_complete_portal_app_flow(env, tmp_path, monkeypatch):
    sample = ROOT / 'app-syncshare-test'
    if not sample.exists():
        pytest.skip('Sibling test micro-app is not available')
    manifests = env / 'manifests'
    shutil.copy(sample / 'manifest.json', manifests / 'syncshare-test.json')
    key = rsa.generate_private_key(65537, 2048)
    pem = tmp_path / 'private.pem'
    pem.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                      serialization.NoEncryption()))
    secret = tmp_path / 'service-token'
    secret.write_text('s' * 43)
    public = 'http://localhost:18080'
    portal_cfg = replace(load_config(env / 'gateway.dev.yml'), auth_mode='gateway', dev_users_file=None,
                         gateway=GatewayConfig(public + '/', 'http://gateway:8080/.well-known/jwks.json', public))
    gateway = None
    key_client = httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=gateway.state.assertions.jwks())))
    portal = create_portal(portal_cfg, registry_token_file=secret, gateway_http_client=key_client)
    lookups = []
    upstreams = []
    class Idp:
        def authorization_url(self, **kwargs):
            return 'https://idp.invalid/login'
    with TestClient(portal, base_url='http://portal:8000', follow_redirects=False) as internal:
        def decision(request):
            lookups.append(request)
            response = internal.request(request.method, request.url.path, headers=request.headers, content=request.content)
            return httpx.Response(response.status_code, content=response.content, headers=response.headers)
        registry = RegistryClient('http://portal:8000', secret, transport=httpx.MockTransport(decision))
        cfg = Settings(public, OidcConfig('http://localhost:8180/realms/hka', 'portal', 'test-only',
                                         public + '/oidc/callback', public + '/'), pem,
                       cookie_secure=False, cookie_name='test_sid', login_cookie='test_login',
                       portal_upstream='http://portal:8000', registry_url='http://portal:8000',
                       registry_token_file=secret, apps=AppsConfig('http://app-{slug}:8080'),
                       internal_hosts=('gateway',), role_vocabulary=('student', 'employee', 'platform-admin'))
        monkeypatch.syspath_prepend(str(sample))
        monkeypatch.syspath_prepend(str(sample / 'src'))
        monkeypatch.setenv('PORTAL_BASE_PATH', '/apps/syncshare-test')
        monkeypatch.setenv('PORTAL_DEV', '0')
        monkeypatch.setenv('PORTAL_ENV', 'production')
        monkeypatch.setenv('PORTAL_API_URL', 'http://gateway:8080')
        monkeypatch.setenv('PORTAL_ISSUER', public + '/')
        # Config reads the real supplied manifest; no test changes to that repository.
        monkeypatch.chdir(sample)
        micro = importlib.import_module('app.main')
        micro.views.STORE.clear()
        app_transport = httpx.ASGITransport(app=micro.app)
        async def send_app(request):
            upstreams.append(request)
            return await app_transport.handle_async_request(request)
        gateway = create_gateway(cfg, redis_client=fakeredis.FakeRedis(decode_responses=True), oidc_client=Idp(),
                                 registry_client=registry, app_transport=httpx.MockTransport(send_app),
                                 portal_transport=httpx.ASGITransport(app=portal))
        # SDK uses its normal HTTP/JWKS/nav code, routed to the real ASGI gateway.
        def sdk_client(**kwargs):
            return httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway), **kwargs)
        for name in ('platform_sdk.jwks', 'platform_sdk.layout'):
            module = importlib.import_module(name)
            monkeypatch.setattr(module, 'httpx', SimpleNamespace(AsyncClient=sdk_client, HTTPError=httpx.HTTPError))
        with TestClient(gateway, base_url=public, follow_redirects=False) as browser:
            assert browser.get('/').headers['location'] == 'https://idp.invalid/login'
            user = gateway.state.sessions.create('student-1', 'Group Test', frozenset({'student'}))
            browser.cookies.set(cfg.cookie_name, user.sid)
            home = browser.get('/')
            assert home.status_code == 200 and 'SyncShare' in home.text
            assert 'set-cookie' not in home.headers
            assert browser.get('/_portal/static/icons.svg').status_code == 200
            page = browser.get('/apps/syncshare-test/', headers={'X-Portal-Assertion': 'forged', 'Authorization': 'Bearer browser'})
            assert page.status_code == 200 and 'SyncShare' in page.text
            assert "default-src 'self'" in page.headers['content-security-policy']
            assert upstreams and 'authorization' not in upstreams[-1].headers and 'cookie' not in upstreams[-1].headers
            assert lookups[-1].url.path == '/internal/apps/syncshare-test/authorize'
            assert 'token_use' not in jwt.decode(upstreams[-1].headers['x-portal-assertion'], options={'verify_signature': False})
            assert browser.get('/apps/syncshare-test/static/app.css').status_code == 200
            upload = browser.post('/apps/syncshare-test/upload', files={'datei': ('hello.txt', b'hello group')},
                                  headers={'Origin': public, 'Sec-Fetch-Site': 'same-origin'})
            assert upload.status_code == 200 and 'hello.txt' in upload.text
            file_id = next(iter(micro.views.STORE['student-1']))
            assert browser.get('/apps/syncshare-test/datei/' + file_id).content == b'hello group'
            assert browser.post('/apps/syncshare-test/upload', files={'datei': ('bad.txt', b'bad')},
                                headers={'Origin': 'https://evil.invalid', 'Sec-Fetch-Site': 'cross-site'}).status_code == 403
            other = gateway.state.sessions.create('employee-1', 'Employee', frozenset({'employee'}))
            browser.cookies.set(cfg.cookie_name, other.sid)
            count = len(upstreams)
            assert browser.get('/apps/syncshare-test/').status_code == 403
            assert len(upstreams) == count
            assert browser.get('/internal/apps/syncshare-test/access').status_code == 404
            assert browser.post('/internal/apps/syncshare-test/authorize').status_code == 404
            assert browser.get('/apps/unknown/').status_code == 404
            admin = gateway.state.sessions.create('admin-1', 'Admin', frozenset({'platform-admin'}))
            browser.cookies.set(cfg.cookie_name, admin.sid)
            page = browser.get('/_portal/admin')
            assert page.status_code == 200 and admin.csrf in page.text
            import re
            form_url = next(a for a in re.findall(r'action="([^"]+)"', page.text) if 'noten' in a and 'roles' in a)
            assert browser.post(form_url, data={'roles': 'student', 'csrf': admin.csrf},
                                headers={'Origin': 'https://evil.invalid'}).status_code == 403
            assert browser.post(form_url, data={'roles': 'student', 'csrf': 'wrong'},
                                headers={'Origin': public}).status_code == 400
            assert browser.post(form_url, data={'roles': 'student', 'csrf': admin.csrf},
                                headers={'Origin': public}).status_code == 303
            browser.cookies.set(cfg.cookie_name, user.sid)
            # Changes are evaluated by the portal, not by any gateway role comparison.
            manifest = json.loads((manifests / 'syncshare-test.json').read_text())
            manifest['roles'] = ['employee']
            (manifests / 'syncshare-test.json').write_text(json.dumps(manifest))
            assert browser.get('/apps/syncshare-test/').status_code == 403
            manifest['roles'] = ['student']
            (manifests / 'syncshare-test.json').write_text(json.dumps(manifest))
            state_path = env / 'state.yml'
            state_path.write_text('syncshare-test: {status: unhealthy}\n')
            count = len(upstreams)
            assert browser.get('/apps/syncshare-test/').status_code == 503
            assert len(upstreams) == count
            browser.cookies.clear()
            assert browser.get('/', headers={'X-Portal-Assertion': 'forged'}).status_code == 302
        registry.close()
    key_client.close()
