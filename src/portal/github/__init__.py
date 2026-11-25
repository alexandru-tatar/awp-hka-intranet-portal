"""GitHub-Zugriff des Portals als GitHub App (HKA-82): legt App-Repositories an. Der Schlüssel bleibt im Prozess."""

from .client import GitHubClient, GitHubError

__all__ = ["GitHubClient", "GitHubError"]
