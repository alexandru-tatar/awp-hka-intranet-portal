"""Signaturschlüssel des Identitäts-Tokens und JWKS (02 §7)."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm
from loguru import logger

from ..core.config import AssertionConfig, ConfigError

ALGORITHM: Final = "RS256"
LEEWAY_SECONDS: Final = 5
TOKEN_VERSION: Final = 1
GENERATED_KEY_BITS: Final = 3072


class InvalidAssertion(Exception):
    """Ein Identitäts-Token ist ungültig (Signatur, Aussteller, Zielgruppe, Version oder Laufzeit)."""


@dataclass(frozen=True)
class SigningKey:
    """Ein RSA-Schlüssel mit seiner Kennung.

    :ivar kid: RFC-7638-Fingerabdruck des öffentlichen Schlüssels
    :ivar private: Privater Schlüssel
    :ivar public: Öffentlicher Schlüssel
    """
    kid: str
    private: rsa.RSAPrivateKey
    public: rsa.RSAPublicKey

    @classmethod
    def from_private(cls, private: rsa.RSAPrivateKey) -> "SigningKey":
        """Schlüssel samt Kennung aus einem privaten Schlüssel bilden.

        :param private: Privater RSA-Schlüssel
        :return: Der Schlüssel
        :rtype: SigningKey
        """
        public = private.public_key()
        return cls(kid=thumbprint(public), private=private, public=public)

    def jwk(self) -> dict[str, Any]:
        """Öffentlicher Teil als JWK.

        :return: JWK mit ``kty``, ``n``, ``e``, ``kid``, ``alg`` und ``use``
        :rtype: dict[str, Any]
        """
        jwk: dict[str, Any] = json.loads(RSAAlgorithm.to_jwk(self.public))
        return {**jwk, "kid": self.kid, "alg": ALGORITHM, "use": "sig"}


def thumbprint(public: rsa.RSAPublicKey) -> str:
    """RFC-7638-Fingerabdruck (SHA-256 über ``e``, ``kty``, ``n``) als base64url ohne Auffüllung.

    :param public: Öffentlicher RSA-Schlüssel
    :return: Kennung des Schlüssels
    :rtype: str
    """
    jwk = json.loads(RSAAlgorithm.to_jwk(public))
    canonical = json.dumps({"e": jwk["e"], "kty": jwk["kty"], "n": jwk["n"]}, separators=(",", ":"), sort_keys=True)
    digest = hashlib.sha256(canonical.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _read_private(path: Path) -> rsa.RSAPrivateKey:
    """Privaten RSA-Schlüssel aus einer PEM-Datei lesen.

    :param path: Pfad der PEM-Datei
    :return: Der Schlüssel
    :rtype: rsa.RSAPrivateKey
    :raises ConfigError: Falls die Datei kein unverschlüsselter RSA-Schlüssel ist
    """
    try:
        key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    except (ValueError, TypeError) as exc:
        raise ConfigError(f"signing key {path} is not a readable PEM private key") from exc
    if not isinstance(key, rsa.RSAPrivateKey):
        raise ConfigError(f"signing key {path} is not an RSA key")
    return key


class SigningKeys:
    """Aktueller, nächster und voriger Schlüssel; signiert mit dem aktuellen, veröffentlicht alle."""

    def __init__(
        self,
        current: SigningKey,
        *,
        issuer: str,
        next_: SigningKey | None = None,
        previous: SigningKey | None = None,
    ) -> None:
        """Konstruktor.

        :param current: Schlüssel, mit dem signiert wird
        :param issuer: Wert von ``iss``, den ``verify`` erwartet
        :param next_: Schlüssel, der schon veröffentlicht, aber noch nicht benutzt wird
        :param previous: Schlüssel, der nach einem Wechsel noch veröffentlicht bleibt
        """
        self.current: Final = current
        self.issuer: Final = issuer
        self._published: Final = [k for k in (current, next_, previous) if k is not None]

    @classmethod
    def load(cls, cfg: AssertionConfig, *, dev: bool) -> "SigningKeys":
        """Schlüssel aus den PEM-Dateien laden.

        Ohne ``signing_key_current`` erzeugt ``env: dev`` einen flüchtigen Schlüssel.

        :param cfg: Einstellungen des Tokens
        :param dev: Ob die Umgebung ``dev`` ist
        :return: Die Schlüssel
        :rtype: SigningKeys
        :raises ConfigError: Falls der aktuelle Schlüssel fehlt und die Umgebung nicht ``dev`` ist, oder eine Datei ungültig ist
        """
        if cfg.signing_key_current is not None:
            current = SigningKey.from_private(_read_private(cfg.signing_key_current))
        elif dev:
            current = SigningKey.from_private(rsa.generate_private_key(65537, GENERATED_KEY_BITS))
            logger.warning("signing key generated (temporary, dev only) kid_current={}", current.kid)
        else:
            raise ConfigError("assertion.signing_key_current is required outside env dev")
        extra = {
            name: SigningKey.from_private(_read_private(path))
            for name, path in (("next_", cfg.signing_key_next), ("previous", cfg.signing_key_previous))
            if path is not None
        }
        keys = cls(current, issuer=cfg.issuer, **extra)
        logger.info(
            "key_loaded kid_current={} kid_next={} kid_previous={}",
            current.kid,
            extra["next_"].kid if "next_" in extra else None,
            extra["previous"].kid if "previous" in extra else None,
        )
        return keys

    def sign(self, claims: dict[str, Any]) -> str:
        """Claims mit dem aktuellen Schlüssel signieren.

        :param claims: Inhalt des Tokens
        :return: Kompaktes JWT mit ``alg``, ``typ`` und ``kid`` im Kopf
        :rtype: str
        """
        return jwt.encode(
            claims, self.current.private, algorithm=ALGORITHM, headers={"kid": self.current.kid, "typ": "JWT"}
        )

    def jwks(self) -> dict[str, Any]:
        """Alle veröffentlichten öffentlichen Schlüssel.

        :return: JWKS mit ``keys``
        :rtype: dict[str, Any]
        """
        return {"keys": [k.jwk() for k in self._published]}

    def verify(self, token: str, audience: str) -> dict[str, Any]:
        """Ein vom Portal ausgestelltes Token prüfen (für ``/nav``).

        Nur RS256, ``kid`` muss veröffentlicht sein, ``iss`` muss passen, ``audience`` muss in ``aud``
        stehen, ``v`` muss 1 sein; ``exp`` und ``iat`` mit 5 Sekunden Toleranz.

        :param token: Das JWT
        :param audience: Erwartete Zielgruppe, z. B. ``portal``
        :return: Die Claims
        :rtype: dict[str, Any]
        :raises InvalidAssertion: Falls eine Prüfung scheitert
        """
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise InvalidAssertion("malformed") from exc
        if header.get("alg") != ALGORITHM:
            raise InvalidAssertion("bad algorithm")
        key = next((k for k in self._published if k.kid == header.get("kid")), None)
        if key is None:
            raise InvalidAssertion("unknown key")
        try:
            claims = jwt.decode(
                token,
                key.public,
                algorithms=[ALGORITHM],
                audience=audience,
                issuer=self.issuer,
                leeway=LEEWAY_SECONDS,
                options={"require": ["exp", "iat", "sub", "aud", "iss"]},
            )
        except jwt.PyJWTError as exc:
            raise InvalidAssertion(type(exc).__name__) from exc
        if claims.get("v") != TOKEN_VERSION or not isinstance(claims.get("roles"), list):
            raise InvalidAssertion("unsupported claims")
        return claims
