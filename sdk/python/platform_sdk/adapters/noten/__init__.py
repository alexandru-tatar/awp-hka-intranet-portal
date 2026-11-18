"""Noten der angemeldeten Person. Beschreibung: README.md in diesem Ordner."""

from . import errors
from .client import NotenClient

__all__ = ["NotenClient", "errors"]
