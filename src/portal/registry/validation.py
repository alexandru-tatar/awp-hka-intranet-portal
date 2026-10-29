"""Manifest-Prüfung: das Schema plus die Regeln, die es nicht ausdrücken kann (03 §3)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from jsonschema import Draft202012Validator, ValidationError

from .models import RESERVED_SLUGS


class ManifestInvalid(Exception):
    """Ein Manifest ist ungültig.

    :ivar problems: Alle Probleme als ``<json-pointer>: <meldung>``
    """
    def __init__(self, problems: list[str]):
        """Konstruktor mit den Problemen.

        :param problems: Alle Probleme des Manifests
        """
        super().__init__("; ".join(problems))
        self.problems = problems


def _pointer(error: ValidationError) -> str:
    """JSON-Pointer auf die Fehlerstelle.

    :param error: Fehler der Schema-Prüfung
    :return: Pointer, z. B. ``/menu/icon``
    :rtype: str
    """
    return "/" + "/".join(map(str, error.absolute_path))


class ManifestValidator:
    """Prüft Manifeste gegen das JSON-Schema, die reservierten Slugs, die Rollen und die Adapter-Scopes."""
    def __init__(self, schema_path: Path, role_vocabulary: Iterable[str], adapter_scopes: Iterable[str]):
        """Konstruktor mit Schema und erlaubten Werten.

        :param schema_path: Pfad zum JSON-Schema
        :param role_vocabulary: Erlaubte Rollen
        :param adapter_scopes: Erlaubte Adapter-Scopes
        """
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        self._schema = Draft202012Validator(schema)
        self._roles = frozenset(role_vocabulary)
        self._scopes = frozenset(adapter_scopes)

    def problems(self, manifest: object) -> list[str]:
        """Alle Probleme eines Manifests als ``<json-pointer>: <meldung>``.

        Bei Schemafehlern werden nur diese gemeldet, die weiteren Regeln erst danach.

        :param manifest: Geparstes Manifest
        :return: Probleme, leer bei gültigem Manifest
        :rtype: list[str]
        """
        schema_problems = self._schema_problems(manifest)
        if schema_problems:
            return schema_problems
        return self._registration_problems(manifest)

    def validate(self, manifest: object) -> None:
        """Manifest prüfen.

        :param manifest: Geparstes Manifest
        :raises ManifestInvalid: Falls es Probleme gibt
        """
        problems = self.problems(manifest)
        if problems:
            raise ManifestInvalid(problems)

    def _schema_problems(self, manifest: object) -> list[str]:
        """Probleme gegen das JSON-Schema.

        :param manifest: Geparstes Manifest
        :return: Probleme, nach Pointer sortiert
        :rtype: list[str]
        """
        errors = sorted(self._schema.iter_errors(manifest), key=_pointer)
        return [f"{_pointer(e)}: {e.message}" for e in errors]

    def _registration_problems(self, manifest: dict) -> list[str]:
        """Probleme, die das Schema nicht ausdrücken kann: reservierter Slug, unbekannte Rolle, unbekannter Adapter-Scope.

        :param manifest: Manifest, das dem Schema entspricht
        :return: Probleme
        :rtype: list[str]
        """
        problems = []
        if manifest["slug"] in RESERVED_SLUGS:
            problems.append(f"/slug: '{manifest['slug']}' is reserved")
        problems += [f"/roles: unknown role '{r}'" for r in manifest["roles"] if r not in self._roles]
        problems += [
            f"/adapters: unknown adapter scope '{a}'"
            for a in manifest.get("adapters", [])
            if a not in self._scopes
        ]
        return problems
