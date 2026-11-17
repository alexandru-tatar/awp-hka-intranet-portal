"""Real portal + standalone gateway + supplied SyncShare SDK app (bwSync explorer), in-process only."""
from dataclasses import replace
import importlib
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
import httpx
import jwt
import pytest

from portal.app import create_app as create_portal
from portal.core.config import GatewayConfig, load_config

ROOT = Path(__file__).resolve().parents[2]
fakeredis = pytest.importorskip('fakeredis', reason='Cross-project flow test needs the gateway test dependencies')
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
    base_cfg = load_config(env / 'gateway.dev.yml')
    portal_cfg = replace(base_cfg, auth_mode='gateway', dev_users_file=None,
                         adapter_scopes=(*base_cfg.adapter_scopes, 'bwsync:read', 'bwsync:write', 'bwsync:delete'),
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
        monkeypatch.setenv('PORTAL_ADAPTERS_URL', 'http://adapter:8080')
        # Config reads the real supplied manifest; no test changes to that repository.
        monkeypatch.chdir(sample)
        micro = importlib.import_module('app.main')
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
        # Exercise the real SDK file transport; only the external adapter (bwSync account) is simulated.
        adapter_files = {}
        adapter_folders = set()
        adapter_calls = []
        def adapter_response(request):
            adapter_calls.append((request.method, request.url.path))
            token = request.headers['authorization'].removeprefix('Bearer ')
            claims = gateway.state.assertions.keys.verify(token, 'syncshare-test')
            assert claims['sub'] == 'student-1'
            assert 'adapters' in claims['aud']
            assert set(claims['scp']) == {'bwsync:read', 'bwsync:write', 'bwsync:delete'}
            assert 'x-request-id' in request.headers
            assert 'cookie' not in request.headers
            kind, _, path = request.url.path.removeprefix('/bwsync/').partition('/')
            if (kind, request.method) == ('folders', 'GET'):
                path = path.rstrip('/')
                prefix = path + '/' if path else ''
                children = {k[len(prefix):] for k in (*adapter_files, *adapter_folders) if k.startswith(prefix)}
                entries = [{'name': c, 'type': 'folder' if prefix + c in adapter_folders else 'file',
                            'size': len(adapter_files.get(prefix + c, b'')) if prefix + c in adapter_files else None}
                           for c in sorted(children) if c and '/' not in c]
                return httpx.Response(200, json={'path': path, 'entries': entries, 'truncated': False, 'skipped': 0})
            if (kind, request.method) == ('folders', 'POST'):
                adapter_folders.add(path)
                return httpx.Response(201)
            assert kind == 'files', request.url.path
            if request.method == 'PUT':
                adapter_files[path] = request.content
                return httpx.Response(204)
            if request.method == 'DELETE':
                del adapter_files[path]
                return httpx.Response(204)
            return httpx.Response(200, content=adapter_files[path])
        def adapter_client(**kwargs):
            return httpx.AsyncClient(transport=httpx.MockTransport(adapter_response), **kwargs)
        monkeypatch.setattr(importlib.import_module('platform_sdk.adapters.transport'), 'httpx', SimpleNamespace(
            AsyncClient=adapter_client, HTTPError=httpx.HTTPError, TimeoutException=httpx.TimeoutException))
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
            same_origin = {'Origin': public, 'Sec-Fetch-Site': 'same-origin'}
            made = browser.post('/apps/syncshare-test/ordner', data={'pfad': '', 'name': 'adapter-test'},
                                headers=same_origin)
            assert made.status_code == 303 and made.headers['location'] == '/apps/syncshare-test/?ok=ordner'
            upload = browser.post('/apps/syncshare-test/upload', data={'pfad': 'adapter-test'},
                                  files={'datei': ('hello.txt', b'hello group')}, headers=same_origin)
            assert upload.status_code == 303
            assert upload.headers['location'] == '/apps/syncshare-test/?pfad=adapter-test&ok=hochgeladen'
            listing = browser.get(upload.headers['location'])
            assert listing.status_code == 200 and 'hello.txt' in listing.text
            assert 'Die Datei wurde hochgeladen.' in listing.text
            download = browser.get('/apps/syncshare-test/datei', params={'pfad': 'adapter-test/hello.txt'})
            assert download.content == b'hello group'
            assert download.headers['content-type'] == 'application/octet-stream'
            removed = browser.post('/apps/syncshare-test/loeschen',
                                   data={'pfad': 'adapter-test/hello.txt', 'art': 'datei'}, headers=same_origin)
            assert removed.status_code == 303 and adapter_files == {}
            assert adapter_calls == [('GET', '/bwsync/folders/'),  # first page load lists the top level
                                     ('POST', '/bwsync/folders/adapter-test'),
                                     ('PUT', '/bwsync/files/adapter-test/hello.txt'),
                                     ('GET', '/bwsync/folders/adapter-test'),
                                     ('GET', '/bwsync/files/adapter-test/hello.txt'),
                                     ('DELETE', '/bwsync/files/adapter-test/hello.txt')]
            count = len(adapter_calls)
            assert browser.post('/apps/syncshare-test/upload', files={'datei': ('bad.txt', b'bad')},
                                headers={'Origin': 'https://evil.invalid', 'Sec-Fetch-Site': 'cross-site'}).status_code == 403
            assert len(adapter_calls) == count  # the gateway stops the cross-site upload before the app
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
