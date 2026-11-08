"""Manuelle Registrierung auf der VM mit ``portal-deploy`` (HKA-53, HKA-56): nur ``check``, ``register``, ``list`` und
``remove``, feste Docker-Argumente."""

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
    settings.write_text("PORTAL_IMAGE=hka/portal:test\nMANIFESTS_DIR=/srv/m\nREGISTRY_DIR=/srv/r\nSTATUS_DIR=/srv/s\n")
    base = {"PATH": f"{bin_dir}:/usr/bin:/bin", "PORTAL_DEPLOY_ENV": str(settings),
            "DOCKER_ARGS": str(tmp_path / "docker.args"), "DOCKER_STDIN": str(tmp_path / "docker.stdin"),
            "LOG_FILE": str(tmp_path / "log")}

    class Box:
        args_file = Path(base["DOCKER_ARGS"])
        stdin_file = Path(base["DOCKER_STDIN"])
        log_file = Path(base["LOG_FILE"])

        @staticmethod
        def run(*args: str, stdin: bytes = b'{"slug": "x"}'):
            return subprocess.run([str(SCRIPT), *args], env=dict(base), input=stdin, capture_output=True, timeout=30)

        @staticmethod
        def docker_args() -> list[str]:
            return Box.args_file.read_text().splitlines()

    return Box


@pytest.mark.parametrize("command", [
    "bash", "sh -c id", "check; id", "check bash", "$(id)", "`id`", "CHECK", "Register", "", " check", "check ", "../check",
])
def test_everything_but_the_four_commands_is_refused(box, command):
    result = box.run(command, "--owner", OWNER)
    assert result.returncode == 2
    assert "nur check, register, list oder remove erlaubt" in result.stderr.decode()
    assert not box.args_file.exists()                          # docker wurde nicht aufgerufen
    assert "abgelehnt" in box.log_file.read_text()


@pytest.mark.parametrize("args", [
    (), ("check",), ("check", "--owner"), ("check", "--owner", ""), ("check", "--owner", "ohne-schrägstrich"),
    ("check", "--owner", "a/b c"), ("check", "--owner", "a/b;id"), ("check", "--owner", "a/b$(id)"),
    ("check", "--owner", "../x/y"), ("check", "--owner", "/b"), ("check", "--owner", "a/"),
    ("check", "--owner", OWNER, "extra"), ("check", "--eigentuemer", OWNER), ("check", "--owner=a/b"),
    ("--owner", OWNER, "check"),
    ("list", "extra"), ("list", "--owner", OWNER),
    ("remove",), ("remove", "noten"), ("remove", "noten", "--owner"), ("remove", "--owner", OWNER, "noten"),
    ("remove", "noten", "--owner", "a/b;id"), ("remove", "../x", "--owner", OWNER), ("remove", "Noten", "--owner", OWNER),
    ("remove", "no", "--owner", OWNER), ("remove", "noten;id", "--owner", OWNER), ("remove", "$(id)", "--owner", OWNER),
    ("remove", "noten", "--owner", OWNER, "extra"),
])
def test_arguments_are_checked_before_anything_runs(box, args):
    result = box.run(*args)
    assert result.returncode == 2 and not box.args_file.exists()


def test_check_runs_the_container_read_only_without_network(box):
    result = box.run("check", "--owner", OWNER, stdin=b'{"slug": "noten"}')
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
    assert box.run("register", "--owner", OWNER).returncode == 0
    args = box.docker_args()
    assert "/srv/m:/var/lib/portal/manifests:rw" in args and "/srv/r:/var/lib/portal/registry:rw" in args
    assert args[-5:-2] == ["register", "--config", "/opt/app/dev/gateway.vm.yml"]


def test_list_mounts_everything_read_only_with_the_status_folder(box):
    result = box.run("list", stdin=b"")
    assert result.returncode == 0, result.stderr
    args = box.docker_args()
    assert args[args.index("--network") + 1] == "none" and "--read-only" in args
    assert "/srv/m:/var/lib/portal/manifests:ro" in args and "/srv/r:/var/lib/portal/registry:ro" in args
    assert "/srv/s:/var/lib/portal/status:ro" in args
    assert args[args.index("hka/portal:test") + 1:] == ["-m", "portal.registry", "list", "--config",
                                                        "/opt/app/dev/gateway.vm.yml"]
    assert "list owner=-" in box.log_file.read_text()


def test_list_without_status_folder_still_runs(box, tmp_path):
    (tmp_path / "deploy.env").write_text("PORTAL_IMAGE=hka/portal:test\nMANIFESTS_DIR=/srv/m\nREGISTRY_DIR=/srv/r\n")
    result = box.run("list", stdin=b"")
    assert result.returncode == 0, result.stderr
    assert not any(":/var/lib/portal/status" in arg for arg in box.docker_args())


def test_remove_mounts_writable_and_passes_slug_and_owner(box):
    result = box.run("remove", "noten", "--owner", OWNER, stdin=b"")
    assert result.returncode == 0, result.stderr
    args = box.docker_args()
    assert "/srv/m:/var/lib/portal/manifests:rw" in args and "/srv/r:/var/lib/portal/registry:rw" in args
    assert not any(":/var/lib/portal/status" in arg for arg in args)
    assert args[args.index("hka/portal:test") + 1:] == ["-m", "portal.registry", "remove", "noten", "--config",
                                                        "/opt/app/dev/gateway.vm.yml", "--owner", OWNER]
    assert f"remove slug=noten owner={OWNER}" in box.log_file.read_text()


def test_missing_settings_stop_the_script(box, tmp_path):
    (tmp_path / "deploy.env").write_text("PORTAL_IMAGE=hka/portal:test\n")
    result = box.run("check", "--owner", OWNER)
    assert result.returncode != 0 and b"MANIFESTS_DIR" in result.stderr and not box.args_file.exists()


def test_script_is_executable_and_settings_example_is_complete():
    assert SCRIPT.stat().st_mode & stat.S_IXUSR
    assert SCRIPT.read_text().startswith("#!/bin/bash\n")
    settings = (DEPLOY / "deploy.env.example").read_text()
    assert all(key in settings for key in ("PORTAL_IMAGE=", "MANIFESTS_DIR=", "REGISTRY_DIR="))


def test_script_passes_bash_syntax_check():
    assert subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True).returncode == 0
