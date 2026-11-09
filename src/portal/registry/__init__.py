"""Registry (03-registry.md): Modelle, Manifest-Prüfung, Quellen, Snapshot-Speicher, Prober, Statusdatei und Registrierung."""

from .models import CATEGORIES, RESERVED_SLUGS, STATUSES, AppView, Snapshot
from .prober import Prober
from .status_file import StatusReport, StatusWriter, read_status
from .sources import ManifestDirectorySource, RegistrySource
from .store import Registry
from .validation import ManifestInvalid, ManifestValidator

__all__ = [
    "CATEGORIES", "RESERVED_SLUGS", "STATUSES", "AppView", "Snapshot",
    "ManifestDirectorySource", "RegistrySource", "Registry", "Prober",
    "StatusReport", "StatusWriter", "read_status",
    "ManifestInvalid", "ManifestValidator",
]
