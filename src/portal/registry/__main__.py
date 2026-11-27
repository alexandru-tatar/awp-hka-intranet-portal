"""Befehl zum Registrieren und Verwalten (auf der VM über ``portal-deploy``).

Aufrufe::

    python -m portal.registry check    --config <yml> --owner <owner/repo>   < manifest.json
    python -m portal.registry register --config <yml> --owner <owner/repo>   < manifest.json
    python -m portal.registry list     --config <yml>
    python -m portal.registry remove   <slug> --config <yml> --owner <owner/repo>

``check`` prüft nur, ``register`` legt das Manifest zusätzlich im Manifest-Ordner ab (``registration.py``, HKA-53).
``list`` zeigt alle Apps mit Besitzer und Status aus der Statusdatei, ``remove`` legt eine App still (HKA-56).
Exit-Code 0 = in Ordnung, 1 = abgelehnt (Fehlerblock PF-nnn oder Meldung auf der Fehlerausgabe), 2 = falscher Aufruf,
3 = Fehler im Betrieb der Registry.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Callable, Mapping, TextIO

from loguru import logger

from ..core.config import ConfigError, load_config
from ..core.i18n import current_language
from .cli_texts import cli_language, day, say, stamp
from .registration import MAX_MANIFEST_BYTES, OWNER_RE, SLUG_RE, Entry, NotRegistered, Registrar, RegistryError, Rejected
from .status_file import STALE_AFTER_SECONDS, StatusReport, read_status
from .validation import ManifestValidator

EXIT_OK, EXIT_REJECTED, EXIT_USAGE, EXIT_BROKEN = 0, 1, 2, 3


def _owner(value: str) -> str:
    """Argument ``--owner`` prüfen.

    :param value: Wert aus der Befehlszeile
    :return: Derselbe Wert
    :rtype: str
    :raises argparse.ArgumentTypeError: Falls es nicht die Form ``owner/name`` hat
    """
    if not OWNER_RE.match(value):
        raise argparse.ArgumentTypeError(say("arg.owner_form"))
    return value


def _slug(value: str) -> str:
    """Argument ``slug`` von ``remove`` prüfen.

    :param value: Wert aus der Befehlszeile
    :return: Derselbe Wert
    :rtype: str
    :raises argparse.ArgumentTypeError: Falls es kein gültiger Name einer App ist
    """
    if not SLUG_RE.match(value):
        raise argparse.ArgumentTypeError(say("arg.slug_form"))
    return value


def build_parser() -> argparse.ArgumentParser:
    """Parser der Befehlszeile.

    :return: Der Parser
    :rtype: argparse.ArgumentParser
    """
    parser = argparse.ArgumentParser(prog="python -m portal.registry", description=say("cli.description"))
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", required=True, type=Path, help=say("arg.config"))
    owner = argparse.ArgumentParser(add_help=False)
    owner.add_argument("--owner", required=True, type=_owner, help=say("arg.owner"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", parents=[common, owner], help=say("cmd.check"))
    commands.add_parser("register", parents=[common, owner], help=say("cmd.register"))
    commands.add_parser("list", parents=[common], help=say("cmd.list"))
    remove = commands.add_parser("remove", parents=[common, owner], help=say("cmd.remove"))
    remove.add_argument("slug", type=_slug, help=say("arg.slug"))
    return parser


def render_list(entries: list[Entry], report: StatusReport, now: datetime) -> str:
    """Die Ausgabe von ``list``: eine Tabelle und eine Zeile zum Stand des Status.

    :param entries: Die Apps
    :param report: Inhalt der Statusdatei
    :param now: Aktueller Zeitpunkt mit Zeitzone
    :return: Mehrzeiliger Text
    :rtype: str
    """
    stale = report.is_stale(now)
    rows = [tuple(say(f"list.{name}") for name in ("slug", "owner", "version", "status", "last_probe"))]
    for entry in entries:
        if entry.retired_at is not None:
            status, probe = say("list.retired_since", date=day(entry.retired_at)), "-"
        else:
            app = report.apps.get(entry.slug, {})
            status = say("list.unknown") if stale else str(app.get("status") or say("list.not_taken"))
            probe = str(app.get("last_probe_at") or "-") if not stale else "-"
        rows.append((entry.slug, entry.owner or say("list.no_owner"), entry.version or "-", status, probe))
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    lines = ["  ".join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip() for row in rows]
    if not entries:
        lines.append(say("list.none"))
    if report.written_at is None:
        lines.append(say("list.no_status_file"))
    elif stale:
        lines.append(say("list.stale", seconds=int(STALE_AFTER_SECONDS), stamp=stamp(report.written_at)))
    else:
        lines.append(say("list.status_from", stamp=stamp(report.written_at)))
    return "\n".join(lines)


def main(argv: list[str] | None = None, stdin: BinaryIO | None = None,
         stdout: TextIO | None = None, stderr: TextIO | None = None,
         now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
         env: Mapping[str, str] | None = None) -> int:
    """Befehl ausführen, in der Sprache aus ``PORTAL_LANG`` bzw. ``LC_ALL``, ``LC_MESSAGES``, ``LANG`` (siehe ``cli_texts``).

    :param argv: Argumente, sonst ``sys.argv``
    :param stdin: Eingabe mit dem Manifest, sonst ``sys.stdin.buffer``
    :param stdout: Ausgabe, sonst ``sys.stdout``
    :param stderr: Fehlerausgabe, sonst ``sys.stderr``
    :param now: Uhr für Stilllegung, Sperrfrist und das Alter der Statusdatei
    :param env: Umgebungsvariablen für die Sprache, sonst ``os.environ``
    :return: Exit-Code
    :rtype: int
    """
    token = current_language.set(cli_language(env))
    try:
        return _run(argv, stdin, stdout, stderr, now)
    finally:
        current_language.reset(token)


def _run(argv: list[str] | None, stdin: BinaryIO | None, stdout: TextIO | None, stderr: TextIO | None,
         now: Callable[[], datetime]) -> int:
    """Befehl ausführen (``main`` setzt vorher die Sprache).

    :param argv: Argumente, sonst ``sys.argv``
    :param stdin: Eingabe mit dem Manifest, sonst ``sys.stdin.buffer``
    :param stdout: Ausgabe, sonst ``sys.stdout``
    :param stderr: Fehlerausgabe, sonst ``sys.stderr``
    :param now: Uhr für Stilllegung, Sperrfrist und das Alter der Statusdatei
    :return: Exit-Code
    :rtype: int
    """
    out, err = stdout or sys.stdout, stderr or sys.stderr
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return EXIT_USAGE if exc.code else EXIT_OK
    logger.remove()
    try:
        cfg = load_config(args.config)
    except (ConfigError, OSError) as exc:
        print(say("err.config", detail=exc), file=err)
        return EXIT_BROKEN
    if cfg.registry.owners_file is None:
        print(say("err.owners_missing"), file=err)
        return EXIT_BROKEN
    registrar = Registrar(
        cfg.manifests_dir,
        cfg.registry.owners_file,
        ManifestValidator(cfg.schema_path, cfg.role_vocabulary, cfg.adapter_scopes),
        cfg.role_vocabulary,
        now=now,
    )
    try:
        if args.command == "list":
            print(render_list(registrar.entries(), read_status(cfg.registry.status_file), now()), file=out)
        elif args.command == "remove":
            registrar.remove(args.slug, args.owner)
            print(say("ok.removed", slug=args.slug), file=out)
        else:
            raw = (stdin or sys.stdin.buffer).read(MAX_MANIFEST_BYTES + 1)
            if args.command == "check":
                manifest = registrar.check(raw, args.owner)
                print(say("ok.valid", slug=manifest["slug"], version=manifest["version"]), file=out)
            else:
                manifest, known = registrar.register(raw, args.owner)
                print(say("ok.registered", slug=manifest["slug"], version=manifest["version"],
                          what=say("ok.updated" if known else "ok.new")), file=out)
    except Rejected as exc:
        print(exc.render(), file=err)
        return EXIT_REJECTED
    except NotRegistered as exc:
        print(say("err.not_registered", slug=exc), file=err)
        return EXIT_REJECTED
    except RegistryError as exc:
        print(say("err.registry", detail=exc), file=err)
        return EXIT_BROKEN
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
