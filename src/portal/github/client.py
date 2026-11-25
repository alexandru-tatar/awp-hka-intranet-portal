"""GitHubClient: die wenigen GitHub-Aufrufe, die das Anlegen einer App braucht (``tools/neue-app.sh`` als Vorbild).

Der private Schlüssel der GitHub App wird nur beim Start aus der Datei gelesen und nie ausgegeben. Fehler tragen
nur den Namen des Schrittes und den HTTP-Status, nie Header, Token oder Antworttexte.
"""

from __future__ import annotations

import base64
import threading
import time
from typing import Any, Callable, Final

import httpx
import jwt
from cryptography.hazmat.primitives import serialization

from ..core.config import AppCreationConfig

API_VERSION: Final = "2022-11-28"
JWT_LIFETIME_SECONDS: Final = 540  # GitHub erlaubt höchstens 10 Minuten
TOKEN_MARGIN_SECONDS: Final = 120  # Installationstoken früh genug erneuern


class GitHubError(Exception):
    """Ein GitHub-Aufruf ist fehlgeschlagen. Der Text enthält nie Token, Header oder Antworttexte.

    :ivar op: Name des Aufrufs, zum Beispiel ``create_ruleset``
    :ivar status: HTTP-Status oder ``None`` bei einem Verbindungsfehler
    """

    def __init__(self, op: str, status: int | None = None) -> None:
        """:param op: Name des Aufrufs
        :param status: HTTP-Status, ``None`` bei Verbindungsfehler
        """
        super().__init__(f"GitHub {op} fehlgeschlagen" + (f" (HTTP {status})" if status is not None else " (keine Verbindung)"))
        self.op: str = op
        self.status: int | None = status


class GitHubClient:
    """Spricht als GitHub App (Installationstoken) mit der GitHub-API."""

    def __init__(self, cfg: AppCreationConfig, http: httpx.Client | None = None,
                 clock: Callable[[], float] = time.time) -> None:
        """Konstruktor; liest den privaten Schlüssel.

        :param cfg: Einstellungen des Abschnitts ``app_creation``
        :param http: Fertiger HTTP-Client, in Tests mit ``httpx.MockTransport``
        :param clock: Uhr in Sekunden, für Tests
        :raises ValueError: Falls die Schlüsseldatei kein privater RSA-Schlüssel im PEM-Format ist (ohne Inhalt in der Meldung)
        """
        self._cfg = cfg
        self._http = http or httpx.Client(base_url=cfg.github_api_url, timeout=15, follow_redirects=False, trust_env=False)
        self._owned = http is None
        self._clock = clock
        try:
            self._key = serialization.load_pem_private_key(cfg.private_key_file.read_bytes(), password=None)
        except (OSError, ValueError, TypeError):
            raise ValueError("Der private Schlüssel der GitHub App ist nicht lesbar oder kein PEM-Schlüssel") from None
        self._token: str | None = None
        self._token_expires = 0.0
        self._lock = threading.Lock()

    def __repr__(self) -> str:
        return f"GitHubClient(app_id={self._cfg.app_id})"

    def close(self) -> None:
        """Den eigenen HTTP-Client schließen."""
        if self._owned:
            self._http.close()

    # ── Anmeldung als GitHub App ───────────────────────────────────────────────────────────────

    def _app_jwt(self) -> str:
        now = int(self._clock())
        return jwt.encode({"iat": now - 60, "exp": now + JWT_LIFETIME_SECONDS, "iss": str(self._cfg.app_id)},
                          self._key, algorithm="RS256")

    def _installation_token(self) -> str:
        with self._lock:
            if self._token is None or self._clock() >= self._token_expires - TOKEN_MARGIN_SECONDS:
                response = self._send("installation_token", "POST",
                                      f"/app/installations/{self._cfg.installation_id}/access_tokens",
                                      headers={"Authorization": f"Bearer {self._app_jwt()}"}, expect=(201,))
                data = response.json()
                token = data.get("token")
                if not isinstance(token, str) or not token:
                    raise GitHubError("installation_token", response.status_code)
                self._token = token
                self._token_expires = self._clock() + 3300  # Token gelten eine Stunde
            return self._token

    def _send(self, op: str, method: str, path: str, *, headers: dict[str, str] | None = None,
              json: Any = None, expect: tuple[int, ...] = (200,)) -> httpx.Response:
        merged = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": API_VERSION, **(headers or {})}
        try:
            response = self._http.request(method, path, headers=merged, json=json)
        except httpx.HTTPError:
            raise GitHubError(op) from None
        if response.status_code not in expect:
            raise GitHubError(op, response.status_code)
        return response

    def _call(self, op: str, method: str, path: str, *, json: Any = None,
              expect: tuple[int, ...] = (200,)) -> httpx.Response:
        return self._send(op, method, path, headers={"Authorization": f"Bearer {self._installation_token()}"},
                          json=json, expect=expect)

    # ── Aufrufe ────────────────────────────────────────────────────────────────────────────────

    def repo(self, owner: str, name: str) -> dict | None:
        """Ein Repository lesen.

        :param owner: Konto
        :param name: Name des Repositorys
        :return: Die Antwort von GitHub oder ``None``, falls es das Repository nicht gibt
        :rtype: dict | None
        :raises GitHubError: Bei anderen Fehlern
        """
        response = self._call("repo", "GET", f"/repos/{owner}/{name}", expect=(200, 404))
        return response.json() if response.status_code == 200 else None

    def generate_from_template(self, template_owner: str, template: str, owner: str, name: str, *,
                               description: str, private: bool) -> None:
        """Aus einer Vorlage ein neues Repository anlegen (nur der Standardzweig kommt mit).

        :param template_owner: Konto der Vorlage
        :param template: Name der Vorlage
        :param owner: Konto des neuen Repositorys
        :param name: Name des neuen Repositorys
        :param description: Beschreibung
        :param private: ``True`` für ein privates Repository
        :raises GitHubError: Bei Fehlern
        """
        self._call("generate", "POST", f"/repos/{template_owner}/{template}/generate", expect=(201,),
                   json={"owner": owner, "name": name, "description": description, "private": private,
                         "include_all_branches": False})

    def file(self, repo: str, path: str, ref: str = "main") -> tuple[str, str] | None:
        """Eine Datei lesen.

        :param repo: ``konto/name``
        :param path: Pfad der Datei
        :param ref: Zweig
        :return: Inhalt und Blob-SHA oder ``None``, falls es die Datei noch nicht gibt
        :rtype: tuple[str, str] | None
        :raises GitHubError: Bei anderen Fehlern
        """
        response = self._call("contents", "GET", f"/repos/{repo}/contents/{path}?ref={ref}", expect=(200, 404))
        if response.status_code == 404:
            return None
        data = response.json()
        try:
            return base64.b64decode(data["content"]).decode("utf-8"), data["sha"]
        except (KeyError, ValueError, TypeError):
            raise GitHubError("contents", response.status_code) from None

    def put_file(self, repo: str, path: str, text: str, sha: str, message: str, branch: str = "main") -> None:
        """Eine vorhandene Datei ersetzen.

        :param repo: ``konto/name``
        :param path: Pfad der Datei
        :param text: Neuer Inhalt
        :param sha: Blob-SHA der alten Datei
        :param message: Commit-Nachricht
        :param branch: Zweig
        :raises GitHubError: Bei Fehlern
        """
        self._call("put_file", "PUT", f"/repos/{repo}/contents/{path}", expect=(200, 201), json={
            "message": message, "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
            "sha": sha, "branch": branch})

    def branch_sha(self, repo: str, branch: str) -> str:
        """Den Commit eines Zweigs lesen.

        :param repo: ``konto/name``
        :param branch: Zweig
        :return: SHA des Commits
        :rtype: str
        :raises GitHubError: Bei Fehlern
        """
        response = self._call("branch_sha", "GET", f"/repos/{repo}/git/ref/heads/{branch}")
        try:
            return response.json()["object"]["sha"]
        except (KeyError, TypeError):
            raise GitHubError("branch_sha", response.status_code) from None

    def create_branch(self, repo: str, branch: str, sha: str) -> None:
        """Einen Zweig anlegen.

        :param repo: ``konto/name``
        :param branch: Name des neuen Zweigs
        :param sha: Commit, auf den er zeigt
        :raises GitHubError: Bei Fehlern
        """
        self._call("create_branch", "POST", f"/repos/{repo}/git/refs", expect=(201,),
                   json={"ref": f"refs/heads/{branch}", "sha": sha})

    def add_topic(self, repo: str, topic: str) -> None:
        """Ein Thema ergänzen, vorhandene bleiben.

        :param repo: ``konto/name``
        :param topic: Thema
        :raises GitHubError: Bei Fehlern
        """
        names = self._call("topics", "GET", f"/repos/{repo}/topics").json().get("names", [])
        if topic not in names:
            self._call("add_topic", "PUT", f"/repos/{repo}/topics", json={"names": [*names, topic]})

    def invite_collaborator(self, repo: str, login: str, permission: str = "push") -> None:
        """Eine Person einladen.

        :param repo: ``konto/name``
        :param login: GitHub-Name der Person
        :param permission: Recht im Repository
        :raises GitHubError: Bei Fehlern, auch bei einem unbekannten Namen (HTTP 404)
        """
        self._call("invite_collaborator", "PUT", f"/repos/{repo}/collaborators/{login}", expect=(201, 204),
                   json={"permission": permission})

    def create_ruleset(self, repo: str, ruleset: dict) -> None:
        """Ein Ruleset anlegen.

        :param repo: ``konto/name``
        :param ruleset: Nutzlast für ``POST /repos/{repo}/rulesets``
        :raises GitHubError: Bei Fehlern
        """
        self._call("create_ruleset", "POST", f"/repos/{repo}/rulesets", expect=(201,), json=ruleset)
