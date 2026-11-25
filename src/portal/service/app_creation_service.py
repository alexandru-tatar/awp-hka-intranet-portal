"""AppCreationService: eine App über die GitHub App anlegen (HKA-82). Ablauf wie ``tools/neue-app.sh``.

Alle Prüfungen laufen vor dem ersten Schreiben. Danach: Name reservieren, Repository aus dem Golden Master anlegen,
Slug im Manifest setzen, Zweig ``develop``, Thema, Person einladen, zuletzt das Ruleset auf ``main`` (danach ist
kein direkter Push mehr möglich). Scheitert ein Schritt nach dem Anlegen, wird nichts gelöscht.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Callable, Final

from loguru import logger

from ..core.config import AppCreationConfig
from ..github import GitHubClient, GitHubError
from ..registry import RESERVED_SLUGS
from ..registry.registration import SLUG_RE, Registrar, RegistryError, Rejected
from .audit import AuditLog
from .exceptions import AppCreationFailedError, InvalidAppRequestError, NotAllowedError, SlugTakenError
from .session_dto import SessionDTO

GITHUB_ACTIONS_ID: Final = 15368
RULESET_NAME: Final = "main-schutz"
PLACEHOLDER_SLUGS: Final = frozenset({"meine-app", "andere-app"})  # Platzhalter der Golden Master, wie ``GESPERRT`` im Skript
LOGIN_RE: Final = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")  # GitHub-Benutzername
_SLUG_VALUE_RE: Final = re.compile(r'("slug"\s*:\s*")[^"]*(")')


@dataclass(frozen=True, slots=True)
class CreateAppRequest:
    """Eingabe zum Anlegen einer App.

    :ivar slug: Kurzname der App
    :ivar language: ``python`` oder ``js``
    :ivar github_login: GitHub-Name der Person, die eingeladen wird
    """
    slug: str
    language: str
    github_login: str


@dataclass(frozen=True, slots=True)
class CreatedAppDTO:
    """Eine angelegte App.

    :ivar slug: Kurzname
    :ivar repo: ``konto/name``
    :ivar url: Adresse des Repositorys
    :ivar template: Repository des Golden Master
    """
    slug: str
    repo: str
    url: str
    template: str


def main_ruleset(check_name: str) -> dict:
    """Die Nutzlast des Rulesets ``main-schutz`` (wie in ``tools/neue-app.sh``).

    :param check_name: Name des Pflicht-Checks
    :return: Nutzlast für ``POST /repos/{repo}/rulesets``
    :rtype: dict
    """
    return {
        "name": RULESET_NAME, "target": "branch", "enforcement": "active", "bypass_actors": [],
        "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {"type": "pull_request", "parameters": {
                "required_approving_review_count": 1, "dismiss_stale_reviews_on_push": True,
                "require_code_owner_review": False, "require_last_push_approval": True,
                "required_review_thread_resolution": False, "allowed_merge_methods": ["merge", "squash", "rebase"]}},
            {"type": "required_status_checks", "parameters": {
                "strict_required_status_checks_policy": False,
                "required_status_checks": [{"context": check_name, "integration_id": GITHUB_ACTIONS_ID}]}},
        ],
    }


class AppCreationService:
    """Legt App-Repositories an. Prüft die Rolle, die Eingabe und den Namen vor jedem Schreiben."""

    def __init__(self, cfg: AppCreationConfig, github: GitHubClient, registrar: Registrar, audit: AuditLog, *,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        """Konstruktor.

        :param cfg: Einstellungen des Abschnitts ``app_creation``
        :param github: Client der GitHub App
        :param registrar: Reserviert den Namen in der Besitzerdatei
        :param audit: Protokoll der Anlagen
        :param sleep: Wartefunktion, für Tests
        """
        self._cfg = cfg
        self._github = github
        self._registrar = registrar
        self._audit = audit
        self._sleep = sleep

    def may_create(self, session: SessionDTO) -> bool:
        """Ob die Person Apps anlegen darf.

        :param session: Session der Person
        :return: ``True``, falls sie eine Rolle aus ``creator_roles`` hat
        :rtype: bool
        """
        return bool(set(session.roles) & set(self._cfg.creator_roles))

    def check_allowed(self, session: SessionDTO) -> None:
        """Die Rolle prüfen und einen Verstoß festhalten.

        :param session: Session der Person
        :raises NotAllowedError: Falls keine Rolle aus ``creator_roles`` vorliegt
        """
        if not self.may_create(session):
            self._audit_safely("app_creation_rejected", session.sub, reason="role")
            raise NotAllowedError

    def create(self, request: CreateAppRequest, session: SessionDTO) -> CreatedAppDTO:
        """Eine App anlegen.

        :param request: Eingabe
        :param session: Session der Person
        :return: Die angelegte App
        :rtype: CreatedAppDTO
        :raises NotAllowedError: Falls die Rolle fehlt (403)
        :raises InvalidAppRequestError: Bei ungültigem Slug, ungültiger Sprache oder ungültigem GitHub-Namen (422)
        :raises SlugTakenError: Falls der Name oder das Repository vergeben ist (409); es wurde nichts angelegt
        :raises AppCreationFailedError: Falls ein Schritt scheitert (502); ``created`` sagt, ob das Repository existiert
        """
        self.check_allowed(session)
        actor, slug = session.sub, request.slug
        try:
            self._validate(request)
        except InvalidAppRequestError as exc:
            self._audit_safely("app_creation_rejected", actor, slug=slug[:40], reason=exc.key)
            raise
        template = self._cfg.templates[request.language]
        repo = f"{self._cfg.owner}/app-{slug}"
        url = f"https://github.com/{repo}"
        owner_ref = repo  # Besitzer der Reservierung: das Repository, das entstehen soll

        # Teil A: nur lesen. Hier darf nichts entstehen.
        step = "pruefen"
        try:
            step = "vorlage"
            template_repo = self._github.repo(self._cfg.template_owner, template)
            if template_repo is None or not template_repo.get("is_template"):
                raise AppCreationFailedError("vorlage")
            step = "repository"
            if self._github.repo(self._cfg.owner, f"app-{slug}") is not None:
                self._audit_safely("app_creation_rejected", actor, slug=slug, reason="repo_exists")
                raise SlugTakenError(slug)
        except GitHubError as exc:
            self._audit_safely("app_creation_failed", actor, slug=slug, step=exc.op)
            raise AppCreationFailedError(step) from None
        except AppCreationFailedError:
            self._audit_safely("app_creation_failed", actor, slug=slug, step=step)
            raise

        try:
            reserved = self._registrar.reserve(slug, owner_ref)
        except Rejected as exc:
            if exc.code != "PF-202":  # PF-204: eine andere Registrierung läuft gerade
                self._audit_safely("app_creation_failed", actor, slug=slug, step="reservieren")
                raise AppCreationFailedError("reservieren") from None
            self._audit_safely("app_creation_rejected", actor, slug=slug, reason="slug_taken")
            raise SlugTakenError(slug) from None
        except (RegistryError, ValueError):
            self._audit_safely("app_creation_failed", actor, slug=slug, step="reservieren")
            raise AppCreationFailedError("reservieren") from None

        try:
            self._audit.record("app_creation_started", actor, slug=slug, repo=repo, template=template)
        except OSError:
            self._release(slug, owner_ref, reserved)
            logger.error("audit_write_failed slug={}", slug)
            raise AppCreationFailedError("protokollieren") from None

        # Teil B: anlegen.
        created = False
        try:
            step = "anlegen"
            self._github.generate_from_template(
                self._cfg.template_owner, template, self._cfg.owner, f"app-{slug}",
                description=f"HKA-Portal-App {slug} (aus dem Golden Master)", private=self._cfg.private)
            created = True
            step = "warten"
            text, sha = self._wait_for_manifest(repo)
            step = "slug"
            self._github.put_file(repo, "manifest.json", self._with_slug(text, slug), sha,
                                  f"Slug auf {slug} gesetzt (Portal)")
            step = "develop"
            self._github.create_branch(repo, "develop", self._github.branch_sha(repo, "main"))
            step = "topic"
            self._github.add_topic(repo, self._cfg.topic)
            step = "einladen"
            self._github.invite_collaborator(repo, request.github_login)
            step = "ruleset"
            self._github.create_ruleset(repo, main_ruleset(self._cfg.check_name))
        except (GitHubError, _StepError) as exc:
            if not created:
                self._release(slug, owner_ref, reserved)
            self._audit_safely("app_creation_failed", actor, slug=slug, repo=repo, template=template, step=step)
            logger.warning("app_creation_failed slug={} step={} cause={}", slug, step, exc)
            raise AppCreationFailedError(step, repo=repo if created else None, url=url if created else None,
                                         created=created) from None

        self._audit_safely("app_created", actor, slug=slug, repo=repo, template=template)
        return CreatedAppDTO(slug=slug, repo=repo, url=url, template=template)

    # ── Hilfen ─────────────────────────────────────────────────────────────────────────────────

    def _validate(self, request: CreateAppRequest) -> None:
        if request.language not in self._cfg.templates:
            raise InvalidAppRequestError("language", "language")
        slug = request.slug
        if SLUG_RE.fullmatch(slug) is None:
            raise InvalidAppRequestError("slug_form", "slug")
        if slug in RESERVED_SLUGS or slug in PLACEHOLDER_SLUGS:
            raise InvalidAppRequestError("slug_reserved", "slug")
        if LOGIN_RE.fullmatch(request.github_login) is None:
            raise InvalidAppRequestError("github_login", "github_login")

    def _wait_for_manifest(self, repo: str) -> tuple[str, str]:
        for attempt in range(1, self._cfg.wait_tries + 1):
            found = self._github.file(repo, "manifest.json")
            if found is not None:
                return found
            if attempt < self._cfg.wait_tries:
                self._sleep(self._cfg.wait_seconds)
        raise _StepError("manifest.json erscheint nicht")

    @staticmethod
    def _with_slug(text: str, slug: str) -> str:
        new = _SLUG_VALUE_RE.sub(lambda m: m.group(1) + slug + m.group(2), text, count=1)
        try:
            ok = json.loads(new).get("slug") == slug
        except (ValueError, AttributeError):
            ok = False
        if not ok:
            raise _StepError("Slug nicht ersetzbar")
        return new

    def _release(self, slug: str, owner: str, reserved: bool) -> None:
        if not reserved:
            return
        try:
            self._registrar.release(slug, owner)
        except (Rejected, RegistryError):
            logger.warning("reservation_release_failed slug={}", slug)

    def _audit_safely(self, action: str, actor: str, **details: str | None) -> None:
        try:
            self._audit.record(action, actor, **details)
        except OSError:
            logger.error("audit_write_failed action={}", action)


class _StepError(Exception):
    """Ein Schritt hat sein Ergebnis nicht geliefert (kein GitHub-Fehler). Nur für den Ablauf in ``create``."""
