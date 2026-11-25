"""Ein erfundenes GitHub für die Tests von HKA-82: ``httpx.MockTransport`` mit Zustand, ohne Netz.

Es prüft wie GitHub die Anmeldung als App (RS256-JWT) und den Installationstoken. Jeder Schreibaufruf landet in
``writes``. ``fail`` lässt einen Schritt mit einem Status scheitern, ``slow`` verzögert den Inhalt der Vorlage.
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

INSTALLATION_TOKEN = "ghs_FAKEINSTALLATIONTOKEN0123456789"
BASE_URL = "https://api.github.test"


def make_key_pair() -> tuple[bytes, bytes]:
    """Ein RSA-Schlüsselpaar für die GitHub App der Tests.

    :return: Privater Schlüssel (PEM) und öffentlicher Schlüssel (PEM)
    :rtype: tuple[bytes, bytes]
    """
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption())
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    return private, public


MANIFEST = json.dumps({"slug": "meine-app", "name": "Meine App", "category": "Sonstiges",
                       "menu": {"label": "Meine App", "icon": "info"}, "roles": ["employee"], "version": "0.1.0"},
                      indent=2) + "\n"


@dataclass
class FakeGitHub:
    """Zustand und Aufrufprotokoll des erfundenen GitHub.

    :ivar public_key: Öffentlicher Schlüssel der App (PEM), prüft das JWT
    :ivar app_id: Erwartete Nummer der App
    :ivar installation_id: Erwartete Installation
    :ivar templates: Namen der Vorlagen, die ``is_template`` sind
    :ivar repos: Vorhandene Repositories ``konto/name``
    :ivar fail: Schritt (``generate``, ``put_file``, ``create_branch``, ``topics``, ``invite``, ``ruleset``) und HTTP-Status
    :ivar empty_polls: So oft ist ``manifest.json`` des neuen Repositorys noch nicht da (404)
    :ivar calls: Alle Aufrufe als ``(Methode, Pfad)``
    :ivar writes: Nur die schreibenden Aufrufe als ``(Methode, Pfad, Nutzlast)``
    :ivar authorizations: Die Authorization-Header der Aufrufe, um Lecks zu prüfen
    """
    public_key: bytes
    app_id: int = 4711
    installation_id: int = 99
    templates: tuple[str, ...] = ("hka/awp-hka-gold-python", "hka/awp-hka-gold-js")
    repos: dict[str, dict] = field(default_factory=dict)
    fail: dict[str, int] = field(default_factory=dict)
    empty_polls: int = 0
    calls: list[tuple[str, str]] = field(default_factory=list)
    writes: list[tuple[str, str, object]] = field(default_factory=list)
    authorizations: list[str] = field(default_factory=list)

    def client(self) -> httpx.Client:
        """Ein HTTP-Client, der nur diesen erfundenen GitHub erreicht.

        :return: Der Client mit ``base_url``
        :rtype: httpx.Client
        """
        return httpx.Client(transport=httpx.MockTransport(self.handle), base_url=BASE_URL)

    def _respond(self, status: int, body: object = None) -> httpx.Response:
        return httpx.Response(status, json=body if body is not None else {})

    def handle(self, request: httpx.Request) -> httpx.Response:
        """Einen Aufruf beantworten wie GitHub.

        :param request: Aufruf
        :return: Antwort
        :rtype: httpx.Response
        """
        method, path = request.method, request.url.path
        self.calls.append((method, path))
        auth = request.headers.get("authorization", "")
        self.authorizations.append(auth)
        body = json.loads(request.content) if request.content else None

        if path == f"/app/installations/{self.installation_id}/access_tokens" and method == "POST":
            try:
                claims = jwt.decode(auth.removeprefix("Bearer "), self.public_key, algorithms=["RS256"],
                                    options={"verify_aud": False})
            except jwt.PyJWTError:
                return self._respond(401, {"message": "Bad credentials"})
            if str(claims.get("iss")) != str(self.app_id):
                return self._respond(401, {"message": "Bad credentials"})
            return self._respond(201, {"token": INSTALLATION_TOKEN, "expires_at": "2099-01-01T00:00:00Z"})
        if auth != f"Bearer {INSTALLATION_TOKEN}":
            return self._respond(401, {"message": "Bad credentials"})
        if method != "GET":
            self.writes.append((method, path, body))

        if (m := re.fullmatch(r"/repos/([^/]+)/([^/]+)", path)) and method == "GET":
            full = f"{m[1]}/{m[2]}"
            if full in self.templates:
                return self._respond(200, {"full_name": full, "is_template": True})
            if full in self.repos:
                return self._respond(200, {"full_name": full, "is_template": False})
            return self._respond(404, {"message": "Not Found"})
        if (m := re.fullmatch(r"/repos/([^/]+)/([^/]+)/generate", path)) and method == "POST":
            if "generate" in self.fail:
                return self._respond(self.fail["generate"], {"message": "boom"})
            full = f"{body['owner']}/{body['name']}"
            self.repos[full] = {"manifest": MANIFEST, "sha": "sha-1", "branches": {"main": "c0ffee"}, "topics": [],
                                "collaborators": {}, "rulesets": [], "private": body["private"], "polls": 0,
                                "from": f"{m[1]}/{m[2]}", "description": body["description"]}
            return self._respond(201, {"full_name": full})
        if (m := re.fullmatch(r"/repos/([^/]+/[^/]+)/contents/manifest\.json", path)):
            repo = self.repos.get(m[1])
            if repo is None:
                return self._respond(404)
            if method == "GET":
                if repo["polls"] < self.empty_polls:
                    repo["polls"] += 1
                    return self._respond(404, {"message": "Not Found"})
                return self._respond(200, {"sha": repo["sha"],
                                           "content": base64.b64encode(repo["manifest"].encode()).decode()})
            if "put_file" in self.fail:
                return self._respond(self.fail["put_file"])
            repo["manifest"] = base64.b64decode(body["content"]).decode()
            repo["sha"] = "sha-2"
            return self._respond(200, {})
        if (m := re.fullmatch(r"/repos/([^/]+/[^/]+)/git/ref/heads/([^/]+)", path)) and method == "GET":
            repo = self.repos.get(m[1])
            sha = repo["branches"].get(m[2]) if repo else None
            return self._respond(200, {"object": {"sha": sha}}) if sha else self._respond(404)
        if (m := re.fullmatch(r"/repos/([^/]+/[^/]+)/git/refs", path)) and method == "POST":
            if "create_branch" in self.fail:
                return self._respond(self.fail["create_branch"])
            self.repos[m[1]]["branches"][body["ref"].removeprefix("refs/heads/")] = body["sha"]
            return self._respond(201, {})
        if (m := re.fullmatch(r"/repos/([^/]+/[^/]+)/topics", path)):
            repo = self.repos[m[1]]
            if method == "GET":
                return self._respond(200, {"names": repo["topics"]})
            if "topics" in self.fail:
                return self._respond(self.fail["topics"])
            repo["topics"] = body["names"]
            return self._respond(200, {"names": repo["topics"]})
        if (m := re.fullmatch(r"/repos/([^/]+/[^/]+)/collaborators/([^/]+)", path)) and method == "PUT":
            if "invite" in self.fail:
                return self._respond(self.fail["invite"], {"message": "Not Found"})
            self.repos[m[1]]["collaborators"][m[2]] = body["permission"]
            return self._respond(201, {})
        if (m := re.fullmatch(r"/repos/([^/]+/[^/]+)/rulesets", path)) and method == "POST":
            if "ruleset" in self.fail:
                return self._respond(self.fail["ruleset"], {"message": "Upgrade to GitHub Pro"})
            self.repos[m[1]]["rulesets"].append(body)
            return self._respond(201, {})
        return self._respond(404, {"message": f"unbekannter Aufruf {method} {path}"})
