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
from typing import BinaryIO, Callable, TextIO

from loguru import logger

from ..core.config import ConfigError, load_config
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
        raise argparse.ArgumentTypeError("muss die Form owner/name haben")
    return value


def _slug(value: str) -> str:
    """Argument ``slug`` von ``remove`` prüfen.

    :param value: Wert aus der Befehlszeile
    :return: Derselbe Wert
    :rtype: str
    :raises argparse.ArgumentTypeError: Falls es kein gültiger Name einer App ist
    """
    if not SLUG_RE.match(value):
        raise argparse.ArgumentTypeError("muss ein gültiger Name einer App sein (a-z, 0-9, -)")
    return value


def build_parser() -> argparse.ArgumentParser:
    """Parser der Befehlszeile.

    :return: Der Parser
    :rtype: argparse.ArgumentParser
    """
    parser = argparse.ArgumentParser(prog="python -m portal.registry", description=__doc__.split("\n\n")[0])
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", required=True, type=Path, help="Konfiguration des Portals (YAML)")
    owner = argparse.ArgumentParser(add_help=False)
    owner.add_argument("--owner", required=True, type=_owner, help="Repository, aus dem die App kommt (owner/name)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", parents=[common, owner], help="Manifest von der Standardeingabe prüfen")
    commands.add_parser("register", parents=[common, owner], help="Manifest prüfen und ablegen")
    commands.add_parser("list", parents=[common], help="Alle Apps mit Besitzer und Status zeigen")
    remove = commands.add_parser("remove", parents=[common, owner], help="App stilllegen")
    remove.add_argument("slug", type=_slug, help="Name der App")
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
    rows = [("SLUG", "BESITZER", "VERSION", "STATUS", "LETZTE PRÜFUNG")]
    for entry in entries:
        if entry.retired_at is not None:
            status, probe = f"stillgelegt seit {entry.retired_at:%d.%m.%Y}", "-"
        else:
            app = report.apps.get(entry.slug, {})
            status = "unbekannt" if stale else str(app.get("status") or "noch nicht übernommen")
            probe = str(app.get("last_probe_at") or "-") if not stale else "-"
        rows.append((entry.slug, entry.owner or "(ohne Besitzer)", entry.version or "-", status, probe))
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    lines = ["  ".join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip() for row in rows]
    if not entries:
        lines.append("Keine Apps registriert.")
    if report.written_at is None:
        lines.append("Hinweis: Keine Statusdatei gefunden. Läuft das Portal mit registry.status_file?")
    elif stale:
        lines.append(f"Hinweis: Die Statusdatei ist älter als {int(STALE_AFTER_SECONDS)} s "
                     f"(Stand {report.written_at:%d.%m.%Y %H:%M:%S %Z}). Läuft das Portal?")
    else:
        lines.append(f"Status vom {report.written_at:%d.%m.%Y %H:%M:%S %Z}.")
    return "\n".join(lines)


def main(argv: list[str] | None = None, stdin: BinaryIO | None = None,
         stdout: TextIO | None = None, stderr: TextIO | None = None,
         now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> int:
    """Befehl ausführen.

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
        print(f"FEHLER Konfiguration: {exc}", file=err)
        return EXIT_BROKEN
    if cfg.registry.owners_file is None:
        print("FEHLER Konfiguration: registry.owners_file fehlt", file=err)
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
            print(f"OK slug={args.slug}: Stillgelegt. Das Portal nimmt die App innerhalb weniger Sekunden aus dem "
                  "Menü. Dasselbe Repository kann den Namen jederzeit wieder registrieren.", file=out)
        else:
            raw = (stdin or sys.stdin.buffer).read(MAX_MANIFEST_BYTES + 1)
            if args.command == "check":
                manifest = registrar.check(raw, args.owner)
                print(f"OK slug={manifest['slug']} version={manifest['version']}: Das Manifest ist gültig.", file=out)
            else:
                manifest, known = registrar.register(raw, args.owner)
                print(f"OK slug={manifest['slug']} version={manifest['version']}: "
                      f"{'Aktualisiert' if known else 'Neu registriert'}. Das Portal übernimmt die App innerhalb "
                      "weniger Sekunden und zeigt sie im Menü, sobald /healthz antwortet.", file=out)
    except Rejected as exc:
        print(exc.render(), file=err)
        return EXIT_REJECTED
    except NotRegistered as exc:
        print(f"FEHLER: Die App „{exc}\" ist nicht registriert. Es wurde nichts geändert.\n"
              "Welche Apps registriert sind, zeigt: portal-deploy list", file=err)
        return EXIT_REJECTED
    except RegistryError as exc:
        print(f"FEHLER Registry: {exc}\nBitte das Plattform-Team informieren.", file=err)
        return EXIT_BROKEN
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
