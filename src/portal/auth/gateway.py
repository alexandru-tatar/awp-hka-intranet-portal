"""Public-key-only gateway identity receiver; no login session or signing key."""
from dataclasses import dataclass
import re
import threading
import time

import httpx
import jwt


@dataclass(frozen=True)
class GatewayUser:
    sub: str
    name: str
    roles: frozenset[str]
    csrf: str


class GatewayVerifier:
    def __init__(self, cfg, http=None):
        self.cfg = cfg
        self.http = http or httpx.Client(timeout=2, follow_redirects=False, trust_env=False)
        self.owned = http is None
        self.keys = {}
        self.fetched = float('-inf')
        self.last_fetch = float('-inf')
        self.lock = threading.Lock()

    def close(self):
        if self.owned:
            self.http.close()

    def _key(self, kid):
        with self.lock:
            now = time.monotonic()
            if (kid not in self.keys or now - self.fetched >= 300) and now - self.last_fetch >= 2:
                self.last_fetch = now
                # Bound remote key documents, never follow redirects or token-provided URLs.
                with self.http.stream('GET', self.cfg.jwks_url) as response:
                    response.raise_for_status()
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > 65536:
                            raise ValueError('JWKS too large')
                import json
                keyset = jwt.PyJWKSet.from_dict(json.loads(body))
                self.keys = {k.key_id: k.key for k in keyset.keys
                             if k.key_id and k.key_type == 'RSA' and k.public_key_use in (None, 'sig')}
                self.fetched = now
            if now - self.fetched >= 300 or kid not in self.keys:
                raise ValueError('No current trusted key')
            return self.keys[kid]

    def verify(self, token, *, navigation=False):
        if not token or len(token) > 16384:
            raise ValueError('Invalid assertion')
        header = jwt.get_unverified_header(token)
        if header.get('alg') != 'RS256' or not isinstance(header.get('kid'), str):
            raise ValueError('Invalid algorithm/key')
        claims = jwt.decode(token, self._key(header['kid']), algorithms=['RS256'],
                            issuer=self.cfg.issuer,
                            audience='portal' if navigation else self.cfg.audience,
                            options={'require': ['iss', 'aud', 'sub', 'iat', 'exp', 'jti', 'v', 'roles']})
        if claims['v'] != 1 or not isinstance(claims['sub'], str) or not claims['sub']:
            raise ValueError('Invalid identity')
        if (not isinstance(claims['roles'], list) or
                not all(isinstance(r, str) and re.fullmatch(r'[a-z][a-z0-9-]*', r) for r in claims['roles'])):
            raise ValueError('Invalid roles')
        if not isinstance(claims['jti'], str) or not claims['jti']:
            raise ValueError('Invalid token ID')
        if claims['exp'] <= claims['iat'] or claims['exp'] - claims['iat'] > 300:
            raise ValueError('Invalid assertion lifetime')
        if navigation:
            if claims.get('token_use') is not None or not isinstance(claims.get('azp'), str):
                raise ValueError('Not an app navigation assertion')
        elif claims.get('token_use') != 'portal-ui':
            raise ValueError('Invalid purpose')
        csrf = claims.get('csrf', '')
        if not navigation and (not isinstance(csrf, str) or not re.fullmatch(r'[A-Za-z0-9_-]{22}', csrf)):
            raise ValueError('Missing session-bound CSRF context')
        return GatewayUser(claims['sub'], str(claims.get('name') or claims['sub']),
                           frozenset(claims['roles']), csrf)
