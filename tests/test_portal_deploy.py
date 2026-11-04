"""Festes Kommando des Benutzers ``deploy`` auf der VM (HKA-53, AK5): erlaubt nur ``check`` und ``register``."""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DEPLOY = ROOT / "extras" / "compose" / "vm" / "deploy"
SCRIPT = DEPLOY / "portal-deploy"
OWNER = "alexandru-tatar/meine-app"

pytestmark = [
    pytest.mark.skipif(shutil.which("bash") is None, reason="bash fehlt"),
    pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0,
                       reason="Als root ignoriert das Skript Umgebung und PATH (Absicht)"),
]


@pytest.fixture
def box(tmp_path):
    """Ersatz für ``docker`` und ``logger``, die ihre Aufrufe aufschreiben; dazu eine Einstellungsdatei."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "docker").write_text('#!/bin/bash\nprintf "%s\\n" "$@" > "$DOCKER_ARGS"\ncat > "$DOCKER_STDIN"\n')
    (bin_dir / "logger").write_text('#!/bin/bash\necho "$*" >> "$LOG_FILE"\n')
    for tool in bin_dir.iterdir():
        tool.chmod(0o755)
    settings = tmp_path / "deploy.env"
    settings.write_text("PORTAL_IMAGE=hka/portal:test\nMANIFESTS_DIR=/srv/m\nREGISTRY_DIR=/srv/r\n")
    base = {"PATH": f"{bin_dir}:/usr/bin:/bin", "PORTAL_DEPLOY_ENV": str(settings),
            "DOCKER_ARGS": str(tmp_path / "docker.args"), "DOCKER_STDIN": str(tmp_path / "docker.stdin"),
            "LOG_FILE": str(tmp_path / "log")}

    class Box:
        args_file = Path(base["DOCKER_ARGS"])
        stdin_file = Path(base["DOCKER_STDIN"])
        log_file = Path(base["LOG_FILE"])

        @staticmethod
        def run(command: str | None, *args: str, stdin: bytes = b'{"slug": "x"}'):
            env = dict(base)
            if command is not None:
                env["SSH_ORIGINAL_COMMAND"] = command
            return subprocess.run([str(SCRIPT), *(args or ("--owner", OWNER))], env=env, input=stdin,
                                  capture_output=True, timeout=30)

        @staticmethod
        def docker_args() -> list[str]:
            return Box.args_file.read_text().splitlines()

    return Box


@pytest.mark.parametrize("command", [
    "bash", "sh -c id", "check; id", "check && id", "check bash", "register extra", "check\nbash", "$(id)", "`id`",
    "CHECK", "Register", "", " check", "check ", "../check", "rm -rf /", "scp -t /", "sftp",
])
def test_ak5_everything_but_check_and_register_is_refused(box, command):
    result = box.run(command)
    assert result.returncode == 2
    assert b"nur check oder register erlaubt" in result.stderr
    assert not box.args_file.exists()                          # docker wurde nicht aufgerufen
    assert "abgelehnt" in box.log_file.read_text()


def test_ak5_login_without_command_is_refused(box):
    result = box.run(None)
    assert result.returncode == 2 and not box.args_file.exists()


@pytest.mark.parametrize("args", [
    (), ("--owner",), ("--owner", ""), ("--owner", "ohne-schrägstrich"), ("--owner", "a/b c"), ("--owner", "a/b;id"),
    ("--owner", "a/b$(id)"), ("--owner", "../x/y"), ("--owner", "/b"), ("--owner", "a/"), ("--owner", OWNER, "extra"),
    ("--eigentuemer", OWNER), ("--owner=a/b",),
])
def test_ak5_owner_is_checked_before_anything_runs(box, args):
    result = box.run("check", *args) if args else subprocess.run(
        [str(SCRIPT)], env={"PATH": os.environ["PATH"], "SSH_ORIGINAL_COMMAND": "check"}, capture_output=True)
    assert result.returncode == 2 and not box.args_file.exists()


def test_check_runs_the_container_read_only_without_network(box):
    result = box.run("check", stdin=b'{"slug": "noten"}')
    assert result.returncode == 0, result.stderr
    args = box.docker_args()
    assert args[:2] == ["run", "--rm"] and "-i" in args
    assert args[args.index("--network") + 1] == "none"
    assert "--read-only" in args and args[args.index("--cap-drop") + 1] == "ALL"
    assert "no-new-privileges" in args and "--memory" in args and "--pids-limit" in args
    assert "/srv/m:/var/lib/portal/manifests:ro" in args and "/srv/r:/var/lib/portal/registry:ro" in args
    assert args[args.index("--entrypoint") + 1] == "python"
    tail = args[args.index("hka/portal:test") + 1:]
    assert tail == ["-m", "portal.registry", "check", "--config", "/opt/app/dev/gateway.vm.yml", "--owner", OWNER]
    assert box.stdin_file.read_bytes() == b'{"slug": "noten"}'           # das Manifest kommt im Container an
    assert "check owner=" + OWNER in box.log_file.read_text()


def test_register_mounts_the_folders_writable(box):
    assert box.run("register").returncode == 0
    args = box.docker_args()
    assert "/srv/m:/var/lib/portal/manifests:rw" in args and "/srv/r:/var/lib/portal/registry:rw" in args
    assert args[-5:-2] == ["register", "--config", "/opt/app/dev/gateway.vm.yml"]


def test_owner_comes_from_the_key_not_from_the_command(box):
    result = box.run("register --owner fremd/repo")
    assert result.returncode == 2 and not box.args_file.exists()


def test_missing_settings_stop_the_script(box, tmp_path):
    (tmp_path / "deploy.env").write_text("PORTAL_IMAGE=hka/portal:test\n")
    result = box.run("check")
    assert result.returncode != 0 and b"MANIFESTS_DIR" in result.stderr and not box.args_file.exists()


def test_script_is_executable_and_files_for_the_vm_are_complete():
    assert SCRIPT.stat().st_mode & stat.S_IXUSR
    assert SCRIPT.read_text().startswith("#!/bin/bash\n")
    sudoers = (DEPLOY / "sudoers.portal-deploy").read_text()
    assert "deploy ALL=(root) NOPASSWD: /usr/local/sbin/portal-deploy --owner *" in sudoers
    assert 'env_keep += "SSH_ORIGINAL_COMMAND"' in sudoers and "env_reset" in sudoers
    keys = (DEPLOY / "authorized_keys.example").read_text()
    assert 'restrict,command="sudo -n /usr/local/sbin/portal-deploy --owner ' in keys
    assert "ALL" not in [line.split()[0] for line in sudoers.splitlines() if line and not line.startswith(("#", "Defaults"))]


def test_script_passes_bash_syntax_check():
    assert subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True).returncode == 0
