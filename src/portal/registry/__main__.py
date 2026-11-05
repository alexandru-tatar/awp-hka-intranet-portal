"""Befehl zum Registrieren (auf der VM über ``portal-deploy``): ``python -m portal.registry check|register --config <yml> --owner <owner/repo>``.

Das Manifest kommt auf der Standardeingabe. ``check`` prüft nur, ``register`` legt das Manifest zusätzlich im
Manifest-Ordner ab (``registration.py``). Exit-Code 0 = in Ordnung, 1 = abgelehnt (Fehlerblock PF-nnn auf der
Fehlerausgabe), 2 = falscher Aufruf, 3 = Fehler im Betrieb der Registry.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import BinaryIO, TextIO

from loguru import logger

from ..core.config import ConfigError, load_config
from .registration import MAX_MANIFEST_BYTES, OWNER_RE, Registrar, RegistryError, Rejected
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


def build_parser() -> argparse.ArgumentParser:
    """Parser der Befehlszeile.

    :return: Der Parser
    :rtype: argparse.ArgumentParser
    """
    parser = argparse.ArgumentParser(prog="python -m portal.registry", description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=("check", "register"), help="check prüft, register prüft und legt ab")
    parser.add_argument("--config", required=True, type=Path, help="Konfiguration des Portals (YAML)")
    parser.add_argument("--owner", required=True, type=_owner, help="Repository, aus dem die App kommt (owner/name)")
    return parser


def main(argv: list[str] | None = None, stdin: BinaryIO | None = None,
         stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    """Befehl ausführen.

    :param argv: Argumente, sonst ``sys.argv``
    :param stdin: Eingabe mit dem Manifest, sonst ``sys.stdin.buffer``
    :param stdout: Ausgabe, sonst ``sys.stdout``
    :param stderr: Fehlerausgabe, sonst ``sys.stderr``
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
    )
    raw = (stdin or sys.stdin.buffer).read(MAX_MANIFEST_BYTES + 1)
    try:
        if args.command == "check":
            manifest = registrar.check(raw, args.owner)
            print(f"OK slug={manifest['slug']} version={manifest['version']}: Das Manifest ist gültig.", file=out)
        else:
            manifest, known = registrar.register(raw, args.owner)
            print(f"OK slug={manifest['slug']} version={manifest['version']}: "
                  f"{'Aktualisiert' if known else 'Neu registriert'}. Das Portal übernimmt die App innerhalb weniger "
                  "Sekunden und zeigt sie im Menü, sobald /healthz antwortet.", file=out)
    except Rejected as exc:
        print(exc.render(), file=err)
        return EXIT_REJECTED
    except RegistryError as exc:
        print(f"FEHLER Registry: {exc}\nBitte das Plattform-Team informieren.", file=err)
        return EXIT_BROKEN
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
