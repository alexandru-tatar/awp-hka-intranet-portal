"""bwSync&Share verbinden und trennen: Server-Teil (``server``) und Browser-Skript (``connect.js``), ohne Oberfläche."""

from .server import ABORTED, EXPIRED, POPUP_BLOCKED, ROUTES, SCRIPT, SCRIPT_FILE, SESSION_EXPIRED

__all__ = ["ABORTED", "EXPIRED", "POPUP_BLOCKED", "ROUTES", "SCRIPT", "SCRIPT_FILE", "SESSION_EXPIRED"]
