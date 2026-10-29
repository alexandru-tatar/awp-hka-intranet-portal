"""OIDC-Client: Authorization-URL, Code-Tausch und Prüfung des ID-Tokens (02 §4, §5).

Zugriffs- und Refresh-Token werden nicht aufbewahrt; das ID-Token wird geprüft und seine Claims
werden zurückgegeben.
"""

from __future__ import annotations

import base64
import hashlib
import time
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from loguru import logger
from jwt import PyJWKSet

from ..core.config import OidcConfig

CACHE_SECONDS = 600
TIMEOUT_SECONDS = 5.0


class OidcError(Exception):
    """Fehler bei der Kommunikation mit dem IdP oder bei der Prüfung; der Grund ist nur für das Log bestimmt."""


def pkce_challenge(verifier: str) -> str:
    """PKCE-Challenge (S256) zu einem Verifier berechnen.

    :param verifier: Zufälliger Verifier
    :return: ``BASE64URL(SHA256(verifier))`` ohne Padding
    :rtype: str
    """
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class OidcClient:
    """OIDC-Client für einen IdP (Discovery und JWKS werden zehn Minuten gecacht)."""
    def __init__(self, cfg: OidcConfig, http: httpx.Client | None = None) -> None:
        """Konstruktor mit Einstellungen und HTTP-Client.

        :param cfg: Einstellungen des IdP und des Clients
        :param http: HTTP-Client, sonst ein Client mit fünf Sekunden Timeout
        """
        self._cfg = cfg
        self._http = http or httpx.Client(timeout=TIMEOUT_SECONDS)
        self._discovery: tuple[float, dict[str, Any]] | None = None
        self._jwks: tuple[float, PyJWKSet] | None = None

    def authorization_url(self, *, state: str, nonce: str, verifier: str) -> str:
        """Adresse beim IdP für den Start der Anmeldung (Authorization Code mit PKCE).

        :param state: Zufälliger State
        :param nonce: Zufällige Nonce
        :param verifier: PKCE-Verifier; gesendet wird die Challenge
        :return: Adresse des Authorization-Endpoints mit Query
        :rtype: str
        :raises OidcError: Falls die Discovery fehlschlägt
        """
        query = urlencode({
            "response_type": "code",
            "client_id": self._cfg.client_id,
            "redirect_uri": self._cfg.redirect_uri,
            "scope": " ".join(self._cfg.scopes),
            "state": state,
            "nonce": nonce,
            "code_challenge": pkce_challenge(verifier),
            "code_challenge_method": "S256",
        })
        return f"{self._discover()['authorization_endpoint']}?{query}"

    def claims_for_code(self, *, code: str, verifier: str, nonce: str) -> tuple[dict[str, Any], str]:
        """Den Code gegen ein ID-Token tauschen, das Token prüfen (02 §5) und Claims samt Token liefern.

        :param code: Authorization Code
        :param verifier: PKCE-Verifier der Transaktion
        :param nonce: Nonce der Transaktion
        :return: Claims und das geprüfte ID-Token (wird nur als ``id_token_hint`` für die Abmeldung gebraucht)
        :rtype: tuple[dict[str, Any], str]
        :raises OidcError: Bei jedem Fehler am Token-Endpoint oder bei der Prüfung
        """
        response = self._post_token({
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self._cfg.redirect_uri,
            "code_verifier": verifier,
        })
        id_token = response.get("id_token")
        if not id_token:
            raise OidcError("token response without id_token")
        return self._validate(id_token, nonce), id_token

    def _hint_matches_current_keys(self, id_token: str) -> bool:
        """Ob das ID-Token noch mit den aktuellen Schlüsseln des IdP verifiziert werden kann.

        Der IdP lehnt einen ``id_token_hint`` mit ungültiger Signatur ab (Fehlerseite „Ungültiger Parameter"). Das
        passiert, wenn der IdP seit der Anmeldung neu gestartet wurde oder seine Schlüssel gewechselt hat. Geprüft wird
        gegen eine frisch geladene JWKS; Ablauf, Audience und Nonce zählen nicht, ein abgelaufenes Token ist als Hint erlaubt.

        :param id_token: ID-Token aus der Session
        :return: ``True``, falls die Signatur zu einem aktuellen Schlüssel passt
        :rtype: bool
        """
        try:
            header = jwt.get_unverified_header(id_token)
            if header.get("alg") not in self._cfg.id_token_algs:
                return False
            key = self._signing_key(header.get("kid"), fresh=True)
            jwt.decode(
                id_token,
                key,
                algorithms=list(self._cfg.id_token_algs),
                issuer=self._cfg.issuer,
                options={"verify_exp": False, "verify_iat": False, "verify_nbf": False, "verify_aud": False},
            )
        except (jwt.PyJWTError, OidcError):
            return False
        return True

    def end_session_url(self, id_token: str | None) -> str | None:
        """Adresse beim IdP, die dessen Session beendet (RP-initiated Logout).

        Voraussetzung sind ``post_logout_redirect_uri`` in der Konfiguration und ein ``end_session_endpoint``
        in der Discovery des IdP.

        :param id_token: ID-Token der Anmeldung als ``id_token_hint``; ohne Token oder bei veralteten IdP-Schlüsseln fragt der IdP nach
        :return: Adresse des End-Session-Endpoints mit Query oder ``None``, falls die Abmeldung beim IdP nicht möglich ist
        :rtype: str | None
        """
        if not self._cfg.post_logout_redirect_uri:
            return None
        try:
            endpoint = self._discover().get("end_session_endpoint")
        except OidcError:
            return None
        if not endpoint:
            return None
        params = {"client_id": self._cfg.client_id, "post_logout_redirect_uri": self._cfg.post_logout_redirect_uri}
        if id_token and self._hint_matches_current_keys(id_token):
            params["id_token_hint"] = id_token
        elif id_token:
            logger.warning("logout_without_hint reason=id_token does not match current idp keys")
        return f"{endpoint}?{urlencode(params)}"

    def _post_token(self, data: dict[str, str]) -> dict[str, Any]:
        """Token-Endpoint aufrufen (``client_secret_basic``, ein Retry bei 5xx).

        :param data: Formularfelder der Anfrage
        :return: Antwort des Endpoints
        :rtype: dict[str, Any]
        :raises OidcError: Falls der Endpoint nicht erreichbar ist oder nicht mit 200 antwortet
        """
        endpoint = self._discover()["token_endpoint"]
        auth = (self._cfg.client_id, self._cfg.client_secret)  # client_secret_basic
        for attempt in (1, 2):  # one retry on 5xx
            try:
                response = self._http.post(endpoint, data=data, auth=auth)
            except httpx.HTTPError as exc:
                raise OidcError(f"token endpoint unreachable: {exc}") from exc
            if response.status_code >= 500 and attempt == 1:
                continue
            if response.status_code != 200:
                raise OidcError(f"token endpoint answered {response.status_code}")
            return response.json()
        raise OidcError("token endpoint failed")

    def _validate(self, token: str, nonce: str) -> dict[str, Any]:
        """ID-Token prüfen: Algorithmus, Signatur, ``iss``, ``aud``/``azp``, ``exp``, ``iat``, ``nonce``, ``sub``.

        :param token: Kompaktes JWT
        :param nonce: Erwartete Nonce
        :return: Claims
        :rtype: dict[str, Any]
        :raises OidcError: Falls eine Prüfung fehlschlägt
        """
        try:
            header = jwt.get_unverified_header(token)
            alg = header.get("alg")
            if alg not in self._cfg.id_token_algs:  # also rejects "none" and HMAC
                raise OidcError(f"alg {alg} not allowed")
            key = self._signing_key(header.get("kid"))
            claims = jwt.decode(
                token,
                key,
                algorithms=list(self._cfg.id_token_algs),
                audience=self._cfg.client_id,
                issuer=self._cfg.issuer,
                leeway=self._cfg.clock_leeway_seconds,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise OidcError(f"id_token invalid: {exc}") from exc
        aud = claims["aud"]
        if isinstance(aud, list) and len(aud) > 1 and claims.get("azp") != self._cfg.client_id:
            raise OidcError("azp does not match client_id")
        if claims.get("nonce") != nonce:
            raise OidcError("nonce mismatch")
        if not claims["sub"]:
            raise OidcError("empty sub")
        return claims

    def _discover(self) -> dict[str, Any]:
        """Discovery-Dokument des IdP liefern (zehn Minuten gecacht).

        :return: Inhalt von ``.well-known/openid-configuration``
        :rtype: dict[str, Any]
        :raises OidcError: Falls das Dokument nicht lesbar ist oder der ``issuer`` nicht passt
        """
        now = time.monotonic()
        if self._discovery is None or now - self._discovery[0] > CACHE_SECONDS:
            url = self._cfg.discovery_url or f"{self._cfg.issuer}/.well-known/openid-configuration"
            document = self._get_json(url)
            if document.get("issuer") != self._cfg.issuer:
                raise OidcError("discovery issuer mismatch")
            self._discovery = (now, document)
        return self._discovery[1]

    def _signing_key(self, kid: str | None, *, fresh: bool = False):
        """Öffentlichen Schlüssel zur ``kid`` liefern; bei unbekannter ``kid`` wird die JWKS einmal neu geladen.

        :param kid: Schlüssel-ID aus dem Header des Tokens
        :param fresh: ``True`` ignoriert den Cache und lädt die JWKS immer neu
        :return: Der Schlüssel
        :raises OidcError: Falls die ``kid`` unbekannt bleibt
        """
        now = time.monotonic()
        if not fresh and self._jwks is not None and now - self._jwks[0] <= CACHE_SECONDS:
            found = _find_key(self._jwks[1], kid)
            if found is not None:
                return found.key
        # cache empty, expired, or unknown kid: refetch once
        self._jwks = (now, PyJWKSet.from_dict(self._get_json(self._discover()["jwks_uri"])))
        found = _find_key(self._jwks[1], kid)
        if found is None:
            raise OidcError(f"unknown kid {kid}")
        return found.key

    def _get_json(self, url: str) -> dict[str, Any]:
        """JSON per GET holen.

        :param url: Adresse
        :return: Geparster Inhalt
        :rtype: dict[str, Any]
        :raises OidcError: Bei Netz- oder HTTP-Fehler
        """
        try:
            response = self._http.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise OidcError(f"GET {url} failed: {exc}") from exc


def _find_key(jwks: PyJWKSet, kid: str | None):
    """Schlüssel in einer JWKS suchen.

    :param jwks: Schlüsselmenge
    :param kid: Gesuchte ``kid``; ``None`` nimmt den ersten Schlüssel
    :return: Der Schlüssel oder ``None``
    """
    return next((k for k in jwks.keys if kid is None or k.key_id == kid), None)
