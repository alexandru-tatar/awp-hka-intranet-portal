"""Prüfung der Portal-Assertion (06 §5)."""

from __future__ import annotations

import time

import jwt

from .errors import VerifyError
from .jwks import JwksCache

MAX_TOKEN_BYTES = 8192
LEEWAY_S = 5
_NO_CLAIM_CHECKS = {
    "verify_exp": False,
    "verify_iat": False,
    "verify_nbf": False,
    "verify_aud": False,
    "verify_iss": False,
    "verify_sub": False,
    "verify_jti": False,
}


async def verify(token: str, *, keys: JwksCache, issuer: str, audience: str, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    if not token or len(token) > MAX_TOKEN_BYTES or token.count(".") != 2:
        raise VerifyError("Malformed")
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError:
        raise VerifyError("Malformed") from None
    if header.get("alg") != "RS256":
        raise VerifyError("BadAlgorithm")
    kid = header.get("kid")
    if not kid:
        raise VerifyError("MissingKid")
    try:
        key = await keys.get(kid, now)
    except KeyError:
        raise VerifyError("UnknownKey") from None
    try:
        claims = jwt.decode(token, key, algorithms=["RS256"], options=_NO_CLAIM_CHECKS)
    except jwt.InvalidSignatureError:
        raise VerifyError("BadSignature") from None
    except jwt.PyJWTError:
        raise VerifyError("Malformed") from None

    if claims.get("iss") != issuer:
        raise VerifyError("WrongIssuer")
    aud = claims.get("aud")
    if audience not in (aud if isinstance(aud, list) else [aud]):
        raise VerifyError("WrongAudience")
    if claims.get("v") != 1:
        raise VerifyError("UnsupportedVersion")
    exp, iat = claims.get("exp"), claims.get("iat")
    if not isinstance(exp, int | float) or exp < now - LEEWAY_S:
        raise VerifyError("Expired")
    if not isinstance(iat, int | float) or iat > now + LEEWAY_S:
        raise VerifyError("NotYetValid")
    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub:
        raise VerifyError("MissingSubject")
    roles = claims.get("roles")
    if not isinstance(roles, list) or not all(isinstance(r, str) for r in roles):
        raise VerifyError("BadRoles")
    return claims
