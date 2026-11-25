"""HKA-82: neue App über die GitHub App anlegen (Portal-Seite und JSON-Schnittstelle), ohne echtes GitHub."""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from portal.app import create_app
from portal.core.config import ConfigError, load_config
from portal.registry.registration import Rejected
from conftest import login
from fakes.fake_github import INSTALLATION_TOKEN, MANIFEST, FakeGitHub, make_key_pair

API = "/_portal/api/apps"
PAGE = "/_portal/neue-app"
SECTION = """
app_creation:
  app_id: 4711
  installation_id: 99
  private_key_file: github-app.pem
  owner: hka-apps
  template_owner: hka
  templates: {python: awp-hka-gold-python, js: awp-hka-gold-js}
  audit_file: app-creation.jsonl
  wait_seconds: 0
  wait_tries: 5
"""
GOOD = {"slug": "urlaubsantrag", "language": "python", "github_login": "erika-ersteller"}


class Setup:
    """Anwendung mit erfundenem GitHub, Schlüsseldatei und Protokolldatei."""

    def __init__(self, env, fake: FakeGitHub, private_pem: bytes, section: str = SECTION) -> None:
        self.env, self.fake, self.private_pem = env, fake, private_pem
        cfg = env / "gateway.dev.yml"
        (env / "github-app.pem").write_bytes(private_pem)
        cfg.write_text(cfg.read_text(encoding="utf-8").rstrip("\n") + "\n" + section, encoding="utf-8")
        self.cfg = cfg
        self.client = TestClient(create_app(cfg, github_http_client=fake.client(), sleep=lambda _: None),
                                 follow_redirects=False)

    @property
    def audit(self) -> list[dict]:
        path = self.env / "app-creation.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []

    @property
    def owners(self) -> dict:
        path = self.env / "owners.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def csrf(self) -> str:
        return re.search(r'name="csrf" value="([^"]+)"', self.client.get(PAGE).text).group(1)

    def post_api(self, body: dict | None = None, *, csrf: str | None = None):
        return self.client.post(API, json=GOOD if body is None else body,
                                headers={"X-CSRF-Token": self.csrf() if csrf is None else csrf})


@pytest.fixture(scope="module")
def keys() -> tuple[bytes, bytes]:
    return make_key_pair()


@pytest.fixture
def setup(env, keys) -> Setup:
    return Setup(env, FakeGitHub(public_key=keys[1]), keys[0])


@pytest.fixture
def creator(setup) -> Setup:
    login(setup.client, "ersteller")
    return setup


def writes(setup: Setup) -> list[tuple[str, str, object]]:
    return setup.fake.writes


# ── AK1: das Ergebnis ──────────────────────────────────────────────────────────────────────────


def test_api_creates_repo_with_branches_topic_invitation_and_ruleset(creator):
    r = creator.post_api()
    assert r.status_code == 201, r.text
    assert r.json() == {"slug": "urlaubsantrag", "repo": "hka-apps/app-urlaubsantrag",
                        "url": "https://github.com/hka-apps/app-urlaubsantrag"}
    repo = creator.fake.repos["hka-apps/app-urlaubsantrag"]
    assert repo["from"] == "hka/awp-hka-gold-python" and repo["private"] is False
    assert sorted(repo["branches"]) == ["develop", "main"] and repo["branches"]["develop"] == repo["branches"]["main"]
    assert repo["topics"] == ["hka-app"]
    assert repo["collaborators"] == {"erika-ersteller": "push"}
    assert len(repo["rulesets"]) == 1


def test_manifest_changes_only_the_slug(creator):
    creator.post_api()
    assert creator.fake.repos["hka-apps/app-urlaubsantrag"]["manifest"] == MANIFEST.replace(
        '"meine-app"', '"urlaubsantrag"')


def test_ruleset_is_the_one_of_the_script(creator):
    creator.post_api()
    ruleset = creator.fake.repos["hka-apps/app-urlaubsantrag"]["rulesets"][0]
    assert ruleset["name"] == "main-schutz" and ruleset["enforcement"] == "active" and ruleset["bypass_actors"] == []
    assert ruleset["conditions"]["ref_name"]["include"] == ["refs/heads/main"]
    rules = {rule["type"]: rule.get("parameters") for rule in ruleset["rules"]}
    assert {"deletion", "non_fast_forward"} <= set(rules)
    assert rules["pull_request"]["required_approving_review_count"] == 1
    assert rules["pull_request"]["require_last_push_approval"] is True
    assert rules["required_status_checks"]["required_status_checks"] == [{"context": "check", "integration_id": 15368}]


def test_ruleset_comes_last_because_main_is_locked_afterwards(creator):
    creator.post_api()
    kinds = [(method, path.rsplit("/", 1)[-1]) for method, path, _ in writes(creator)]
    assert kinds[0] == ("POST", "generate") and kinds[-1] == ("POST", "rulesets")
    assert ("PUT", "manifest.json") in kinds[:-1] and ("POST", "refs") in kinds[:-1]


def test_javascript_template_and_private_repo(env, keys):
    section = SECTION + "  private: true\n"
    setup = Setup(env, FakeGitHub(public_key=keys[1]), keys[0], section)
    login(setup.client, "ersteller")
    r = setup.post_api({**GOOD, "language": "js", "slug": "noten-js"})
    assert r.status_code == 201
    repo = setup.fake.repos["hka-apps/app-noten-js"]
    assert repo["from"] == "hka/awp-hka-gold-js" and repo["private"] is True


def test_waits_until_github_has_copied_the_template(env, keys):
    fake = FakeGitHub(public_key=keys[1], empty_polls=3)
    setup = Setup(env, fake, keys[0])
    login(setup.client, "ersteller")
    assert setup.post_api().status_code == 201


def test_gives_up_when_the_template_content_never_arrives(env, keys):
    fake = FakeGitHub(public_key=keys[1], empty_polls=99)
    setup = Setup(env, fake, keys[0])
    login(setup.client, "ersteller")
    r = setup.post_api()
    assert r.status_code == 502 and r.json()["step"] == "warten" and r.json()["created"] is True


def test_registry_reservation_is_bound_to_the_new_repository(creator):
    creator.post_api()
    assert creator.owners == {"urlaubsantrag": "hka-apps/app-urlaubsantrag"}


# ── Die Portal-Seite ───────────────────────────────────────────────────────────────────────────


def test_page_creates_app_and_shows_the_link(creator):
    token = creator.csrf()
    r = creator.client.post(PAGE, data={**GOOD, "csrf": token})
    assert r.status_code == 200
    assert "https://github.com/hka-apps/app-urlaubsantrag" in r.text and "erika-ersteller" in r.text
    assert "hka-apps/app-urlaubsantrag" in creator.fake.repos


def test_page_shows_the_form_with_both_templates(creator):
    r = creator.client.get(PAGE)
    assert r.status_code == 200 and 'value="python"' in r.text and 'value="js"' in r.text
    assert "github-login" in r.text


def test_page_reports_a_bad_slug_next_to_the_field_with_422(creator):
    r = creator.client.post(PAGE, data={**GOOD, "slug": "Ungültig!", "csrf": creator.csrf()})
    assert r.status_code == 422 and 'href="#slug"' in r.text and "Kleinbuchstaben" in r.text
    assert writes(creator) == []


def test_page_reports_a_taken_slug_with_409(creator):
    creator.fake.repos["hka-apps/app-urlaubsantrag"] = {}
    r = creator.client.post(PAGE, data={**GOOD, "csrf": creator.csrf()})
    assert r.status_code == 409 and "schon vergeben" in r.text and writes(creator) == []


def test_page_names_the_failed_step_and_the_existing_repository(creator):
    creator.fake.fail["ruleset"] = 403
    r = creator.client.post(PAGE, data={**GOOD, "csrf": creator.csrf()})
    assert r.status_code == 502 and "Schutz für main" in r.text and "hka-apps/app-urlaubsantrag" in r.text
    assert "Es wurde nichts gelöscht" in r.text and r.text.count("Es wurde nichts gelöscht") == 1   # nur in der Fehlerliste


def test_page_needs_csrf(creator):
    assert creator.client.post(PAGE, data={**GOOD, "csrf": "falsch"}).status_code == 400
    assert writes(creator) == []


def test_header_link_only_for_creators(setup):
    assert PAGE in login(setup.client, "ersteller").get("/").text
    setup.client.cookies.clear()
    assert PAGE in login(setup.client, "admin").get("/").text
    setup.client.cookies.clear()
    assert PAGE not in login(setup.client, "max").get("/").text


# ── AK3: nicht berechtigte Rolle ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize("user", ["alexandru", "max", "neumann", "gast"])
def test_other_roles_get_403_and_nothing_is_created(setup, user):
    login(setup.client, user)
    assert setup.client.get(PAGE).status_code == 403
    assert setup.client.post(PAGE, data={**GOOD, "csrf": "x"}).status_code in (400, 403)
    r = setup.client.post(API, json=GOOD, headers={"X-CSRF-Token": "x"})
    assert r.status_code == 403 and r.headers["content-type"].startswith("application/json")
    assert setup.fake.calls == [] and writes(setup) == [] and setup.owners == {}


def test_api_answers_403_forbidden_for_the_wrong_role_even_with_a_valid_csrf_token(setup):
    login(setup.client, "max")
    token = re.search(r'name="csrf" value="([^"]+)"', setup.client.get("/").text).group(1)   # Formular zum Abmelden
    r = setup.client.post(API, json=GOOD, headers={"X-CSRF-Token": token})
    assert r.status_code == 403 and r.json() == {"error": "forbidden"}
    assert setup.fake.calls == [] and writes(setup) == []


@pytest.mark.parametrize("user", ["ersteller", "admin"])
def test_creator_and_platform_admin_may_create(setup, user):
    login(setup.client, user)
    assert setup.post_api().status_code == 201


def test_without_login_page_redirects_and_api_answers_401(setup):
    assert setup.client.get(PAGE).status_code == 302
    r = setup.client.post(API, json=GOOD, headers={"X-CSRF-Token": "x"})
    assert r.status_code == 401 and r.json() == {"error": "login_required"}
    assert setup.fake.calls == []


def test_api_needs_the_csrf_header(creator):
    r = creator.post_api(csrf="falsch")
    assert r.status_code == 403 and r.json() == {"error": "csrf"} and writes(creator) == []


def test_creator_roles_come_from_the_configuration(env, keys):
    setup = Setup(env, FakeGitHub(public_key=keys[1]), keys[0], SECTION + "  creator_roles: [platform-admin]\n")
    login(setup.client, "ersteller")
    assert setup.client.get(PAGE).status_code == 403
    setup.client.cookies.clear()
    login(setup.client, "admin")
    assert setup.post_api().status_code == 201


# ── AK4: vergebener oder ungültiger Slug, kein Repository ──────────────────────────────────────


@pytest.mark.parametrize("slug", ["", "ab", "Gross", "mit space", "1start", "a" * 32, "unter_strich", "../x"])
def test_invalid_slug_is_rejected_before_anything_is_created(creator, slug):
    r = creator.post_api({**GOOD, "slug": slug})
    assert r.status_code == 422 and r.json()["field"] == "slug"
    assert creator.fake.calls == [] and creator.owners == {}


@pytest.mark.parametrize("slug", ["meine-app", "andere-app", "admin", "apps"])
def test_placeholder_and_reserved_slugs_are_rejected(creator, slug):
    r = creator.post_api({**GOOD, "slug": slug})
    assert r.status_code == 422 and r.json() == {"error": "invalid", "field": "slug", "reason": "slug_reserved"}
    assert creator.fake.calls == []


@pytest.mark.parametrize("body", [
    {**GOOD, "language": "ruby"}, {**GOOD, "github_login": "-bad-"}, {**GOOD, "github_login": "a b"},
    {**GOOD, "github_login": "x" * 40}, {**GOOD, "language": ""},
])
def test_invalid_language_or_github_name_is_rejected(creator, body):
    assert creator.post_api(body).status_code == 422
    assert creator.fake.calls == [] and writes(creator) == []


@pytest.mark.parametrize("body", [[], {"slug": "x"}, {**GOOD, "extra": 1}, {**GOOD, "slug": 5}])
def test_malformed_body_is_422_not_500(creator, body):
    r = creator.post_api(body)
    assert r.status_code == 422 and r.headers["content-type"].startswith("application/json")


def test_slug_of_a_registered_app_is_taken(creator):
    r = creator.post_api({**GOOD, "slug": "noten"})   # dev/manifests/noten.json: von Hand eingerichtet
    assert r.status_code == 409 and r.json() == {"error": "slug_taken"}
    assert writes(creator) == []


def test_slug_reserved_for_another_repository_is_taken(creator):
    (creator.env / "owners.json").write_text(json.dumps({"urlaubsantrag": "andere/app-urlaubsantrag"}), encoding="utf-8")
    r = creator.post_api()
    assert r.status_code == 409 and writes(creator) == []


def test_existing_github_repository_is_taken(creator):
    creator.fake.repos["hka-apps/app-urlaubsantrag"] = {}
    r = creator.post_api()
    assert r.status_code == 409 and writes(creator) == [] and creator.owners == {}


def test_template_that_is_not_a_template_stops_before_any_write(env, keys):
    fake = FakeGitHub(public_key=keys[1], templates=())
    setup = Setup(env, fake, keys[0])
    login(setup.client, "ersteller")
    r = setup.post_api()
    assert r.status_code == 502 and r.json()["created"] is False and r.json()["step"] == "vorlage"
    assert fake.writes == [] and setup.owners == {}


# ── Fehler mitten im Ablauf ────────────────────────────────────────────────────────────────────


def test_failure_before_the_repository_exists_releases_the_name(creator):
    creator.fake.fail["generate"] = 500
    r = creator.post_api()
    assert r.status_code == 502 and r.json()["created"] is False and r.json()["repo"] is None
    assert creator.owners == {}
    creator.fake.fail.clear()
    assert creator.post_api().status_code == 201     # derselbe Name ist wieder frei


@pytest.mark.parametrize("step,fail", [("slug", "put_file"), ("develop", "create_branch"), ("topic", "topics"),
                                       ("einladen", "invite"), ("ruleset", "ruleset")])
def test_failure_after_creation_reports_the_step_and_keeps_everything(creator, step, fail):
    creator.fake.fail[fail] = 500
    r = creator.post_api()
    assert r.status_code == 502
    assert r.json() == {"error": "failed", "step": step, "created": True, "repo": "hka-apps/app-urlaubsantrag",
                        "url": "https://github.com/hka-apps/app-urlaubsantrag"}
    assert "hka-apps/app-urlaubsantrag" in creator.fake.repos                       # nichts gelöscht
    assert not any(method == "DELETE" for method, _, _ in writes(creator))
    assert creator.owners == {"urlaubsantrag": "hka-apps/app-urlaubsantrag"}        # Name bleibt belegt


def test_unknown_github_name_fails_at_the_invitation(creator):
    creator.fake.fail["invite"] = 404
    r = creator.post_api()
    assert r.status_code == 502 and r.json()["step"] == "einladen"


# ── AK5: der Schlüssel der GitHub App bleibt auf dem Server ────────────────────────────────────


def _secrets(setup: Setup) -> list[str]:
    pem = setup.private_pem.decode()
    body = "".join(line for line in pem.splitlines() if "-----" not in line)
    return [INSTALLATION_TOKEN, body[:60], "BEGIN PRIVATE KEY", "BEGIN RSA PRIVATE KEY", "Bearer ghs_", "Bearer eyJ"]


def _all_output(setup: Setup, responses: list, caplog) -> str:
    audit = (setup.env / "app-creation.jsonl")
    return "\n".join([*(r.text + str(dict(r.headers)) for r in responses), caplog.text,
                      audit.read_text(encoding="utf-8") if audit.exists() else ""])


def test_key_and_tokens_never_appear_in_responses_logs_or_audit(creator, caplog):
    responses = [creator.client.get(PAGE), creator.post_api(),
                 creator.client.post(PAGE, data={**GOOD, "slug": "zweite-app", "csrf": creator.csrf()})]
    creator.fake.fail["ruleset"] = 500
    responses.append(creator.post_api({**GOOD, "slug": "dritte-app"}))
    creator.fake.fail["generate"] = 500
    responses.append(creator.post_api({**GOOD, "slug": "vierte-app"}))
    output = _all_output(creator, responses, caplog)
    for secret in _secrets(creator):
        assert secret not in output, secret
    # Der Token wurde wirklich benutzt, sonst wäre die Prüfung leer.
    assert any(INSTALLATION_TOKEN in header for header in creator.fake.authorizations)


def test_github_error_text_has_no_header_and_no_token():
    from portal.github import GitHubError
    text = str(GitHubError("create_ruleset", 403))
    assert text == "GitHub create_ruleset fehlgeschlagen (HTTP 403)" and "Bearer" not in text


def test_client_repr_and_unreadable_key_do_not_print_the_key(env, keys, tmp_path):
    from portal.github import GitHubClient
    setup = Setup(env, FakeGitHub(public_key=keys[1]), keys[0])
    client = setup.client.app.state.portal.github
    assert "BEGIN" not in repr(client) and "4711" in repr(client)
    cfg = load_config(env / "gateway.dev.yml").app_creation
    bad = tmp_path / "kaputt.pem"
    bad.write_text("-----BEGIN PRIVATE KEY-----\nGEHEIM\n-----END PRIVATE KEY-----\n", encoding="utf-8")
    from dataclasses import replace
    with pytest.raises(ValueError) as error:
        GitHubClient(replace(cfg, private_key_file=bad))
    assert "GEHEIM" not in str(error.value) and "BEGIN" not in str(error.value)


def test_jwt_is_signed_with_the_app_key_and_the_wrong_key_is_refused(env, keys):
    other_private, _ = make_key_pair()
    setup = Setup(env, FakeGitHub(public_key=keys[1]), other_private)
    login(setup.client, "ersteller")
    r = setup.post_api()
    assert r.status_code == 502 and r.json()["created"] is False
    assert setup.fake.writes == []


def test_tracebacks_do_not_print_local_variables(tmp_path):
    import io

    from loguru import logger

    from portal.core.config import LoggingConfig
    from portal.core.log import configure_logging
    logfile = tmp_path / "portal.log"
    configure_logging(LoggingConfig(console_level="CRITICAL", file=logfile, file_level="DEBUG"))
    try:
        def boom() -> None:
            private_key = "SEHR-GEHEIM-1234"  # noqa: F841
            raise RuntimeError("x")
        try:
            boom()
        except RuntimeError:
            logger.exception("fehler")
        logger.complete()
        assert "SEHR-GEHEIM-1234" not in logfile.read_text(encoding="utf-8")
    finally:
        logger.remove()
        io.StringIO()


# ── AK6: Protokoll ─────────────────────────────────────────────────────────────────────────────


def test_creation_is_audited_with_who_when_and_which_app(creator):
    creator.post_api()
    actions = [entry["action"] for entry in creator.audit]
    assert actions == ["app_creation_started", "app_created"]
    entry = creator.audit[-1]
    assert entry["actor"] == "dev:ersteller" and entry["slug"] == "urlaubsantrag"
    assert entry["repo"] == "hka-apps/app-urlaubsantrag" and re.fullmatch(r"\d{4}-\d\d-\d\dT[\d:]+\+00:00", entry["ts"])


def test_rejections_and_failures_are_audited_too(creator, setup):
    creator.post_api({**GOOD, "slug": "meine-app"})
    creator.fake.fail["ruleset"] = 500
    creator.post_api({**GOOD, "slug": "kaputt-app"})
    login(setup.client, "ersteller")
    seen = {(entry["action"], entry.get("reason") or entry.get("step")) for entry in creator.audit}
    assert ("app_creation_rejected", "slug_reserved") in seen and ("app_creation_failed", "ruleset") in seen


def test_forbidden_attempt_is_audited(setup):
    login(setup.client, "max")
    assert setup.client.get(PAGE).status_code == 403
    assert [(e["action"], e["reason"], e["actor"]) for e in setup.audit] == [("app_creation_rejected", "role", "dev:max")]


def test_creation_is_refused_when_the_audit_file_cannot_be_written(env, keys):
    section = SECTION.replace("audit_file: app-creation.jsonl", "audit_file: gibt-es-nicht/audit.jsonl")
    setup = Setup(env, FakeGitHub(public_key=keys[1]), keys[0], section)
    login(setup.client, "ersteller")
    r = setup.post_api()
    assert r.status_code == 502 and r.json()["step"] == "protokollieren" and r.json()["created"] is False
    assert setup.fake.writes == [] and setup.owners == {}


# ── Aus, wenn nicht eingerichtet ───────────────────────────────────────────────────────────────


def test_feature_is_off_without_the_section(client):
    login(client, "ersteller")
    assert client.get(PAGE).status_code == 404
    r = client.post(API, json=GOOD, headers={"X-CSRF-Token": "x"})
    assert r.status_code == 404 and r.json() == {"error": "disabled"}
    assert PAGE not in client.get("/").text


# ── Konfiguration ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("change,message", [
    (lambda s: s.replace("  app_id: 4711\n", ""), "missing key app_id"),
    (lambda s: s + "  unbekannt: 1\n", "unknown app_creation key"),
    (lambda s: s.replace("{python: awp-hka-gold-python, js: awp-hka-gold-js}", "{python: x}"), "templates"),
    (lambda s: s + "  creator_roles: [gibt-es-nicht]\n", "not in role_vocabulary"),
    (lambda s: s.replace("github-app.pem", "fehlt.pem"), "private_key_file does not exist"),
    (lambda s: s + "  private: ja\n", "private must be true or false"),
    (lambda s: s + "  github_api_url: ftp://x\n", "github_api_url"),
])
def test_invalid_app_creation_section(env, keys, change, message):
    (env / "github-app.pem").write_bytes(keys[0])
    cfg = env / "gateway.dev.yml"
    cfg.write_text(cfg.read_text(encoding="utf-8").rstrip("\n") + "\n" + change(SECTION), encoding="utf-8")
    with pytest.raises(ConfigError, match=message):
        load_config(cfg)


def test_section_needs_the_owners_file(env, keys):
    (env / "github-app.pem").write_bytes(keys[0])
    cfg = env / "gateway.dev.yml"
    text = cfg.read_text(encoding="utf-8").replace("  owners_file: owners.json\n", "")
    cfg.write_text(text.rstrip("\n") + "\n" + SECTION, encoding="utf-8")
    with pytest.raises(ConfigError, match="owners_file"):
        load_config(cfg)


# ── Registrar: Reservierung ────────────────────────────────────────────────────────────────────


@pytest.fixture
def registrar(setup):
    return setup.client.app.state.portal.app_creation_service._registrar


def test_reserve_binds_the_name_and_is_idempotent_for_the_same_owner(setup, registrar):
    assert registrar.reserve("neue-app", "hka/app-neue-app") is True
    assert registrar.reserve("neue-app", "hka/app-neue-app") is False
    assert setup.owners == {"neue-app": "hka/app-neue-app"}


def test_reserve_refuses_another_owner_with_pf_202(setup, registrar):
    registrar.reserve("neue-app", "hka/app-neue-app")
    with pytest.raises(Rejected) as error:
        registrar.reserve("neue-app", "fremd/app-neue-app")
    assert error.value.code == "PF-202"


def test_release_removes_only_a_reservation_of_the_same_owner_without_manifest(setup, registrar):
    registrar.reserve("neue-app", "hka/app-neue-app")
    assert registrar.release("neue-app", "fremd/x") is False
    assert registrar.release("neue-app", "hka/app-neue-app") is True and setup.owners == {}
    assert registrar.release("neue-app", "hka/app-neue-app") is False


def test_reserve_rejects_malformed_input(registrar):
    with pytest.raises(ValueError):
        registrar.reserve("Neu App", "hka/app-x")
    with pytest.raises(ValueError):
        registrar.reserve("neue-app", "ohne-schrägstrich")
