"""Abbildung der IdP-Claims auf Rollen des Portals (02 §8)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import yaml


@dataclass(frozen=True)
class RoleSource:
    """Eine Quelle für Rollen: ein Claim und seine Wertezuordnung.

    :ivar claim: Name des Claims im ID-Token
    :ivar mapping: Claim-Wert → Rolle
    """
    claim: str
    mapping: Mapping[str, str]


@dataclass(frozen=True)
class RoleMapper:
    """Berechnet die Rollen einer Anmeldung.

    :ivar sources: Zuordnung je Claim
    :ivar default_roles: Rollen, die jeder bekommt (normalerweise leer)
    :ivar grants: Zusätzliche Rollen je Subject
    """
    sources: tuple[RoleSource, ...]
    default_roles: frozenset[str] = frozenset()
    grants: Mapping[str, frozenset[str]] = field(default_factory=dict)

    def map_roles(self, sub: str, claims: Mapping[str, Any]) -> frozenset[str]:
        """Rollen aus den Claims und den Grants ableiten.

        Werte ohne Zuordnung ergeben keine Rolle. Ein Claim darf eine Liste oder ein einzelner Wert sein.

        :param sub: Subject des IdP
        :param claims: Claims des ID-Tokens
        :return: Die Rollen, eventuell leer
        :rtype: frozenset[str]
        """
        roles = set(self.default_roles)
        for source in self.sources:
            value = claims.get(source.claim)
            values = [value] if isinstance(value, str) else (value or [])
            roles.update(source.mapping[v] for v in values if v in source.mapping)
        roles.update(self.grants.get(sub, ()))
        return frozenset(roles)


def load_role_mapper(roles_file: Path, grants_file: Path | None) -> RoleMapper:
    """Zuordnung aus ``roles.yml`` und optional ``grants.yml`` laden.

    :param roles_file: Datei mit ``sources`` und ``default_roles``
    :param grants_file: Datei mit ``grants`` je Subject, optional
    :return: Der Mapper
    :rtype: RoleMapper
    """
    raw = yaml.safe_load(roles_file.read_text(encoding="utf-8")) or {}
    sources = tuple(
        RoleSource(claim=s["claim"], mapping=dict(s.get("map") or {})) for s in raw.get("sources", ())
    )
    grants: dict[str, frozenset[str]] = {}
    if grants_file is not None:
        graw = yaml.safe_load(grants_file.read_text(encoding="utf-8")) or {}
        for g in graw.get("grants", ()):
            grants[g["sub"]] = frozenset(g.get("roles") or ())
    return RoleMapper(
        sources=sources,
        default_roles=frozenset(raw.get("default_roles") or ()),
        grants=grants,
    )
