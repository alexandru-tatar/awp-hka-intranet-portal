"""bwSync&Share verbinden und trennen: Server-Teil.

Verbinden und Trennen laufen im Browser über das Gateway (gleiche Adresse wie die Seite); die App selbst ruft dafür
nichts auf. Ob das Konto verbunden ist, liefert ``portal.adapters.bwsync.is_linked()``.
"""

from __future__ import annotations

# Routen des Gateways (Browser, fetch mit Cookie der Sitzung). Die App gibt sie nicht selbst aus; connect.js kennt sie.
ROUTES = {
    "status": "/connect/bwsync",  # GET: {linked, account}
    "start": "/connect/bwsync/start",  # POST: {login_url, expires_in}
    "poll": "/connect/bwsync/poll",  # POST: {state: pending|linked|none, account}
    "disconnect": "/connect/bwsync",  # DELETE: {linked: false, revoked: true|null|false}
}

# Adresse des Browser-Skripts unter dem Pfad der App: portal.url(SCRIPT)
SCRIPT = "/_sdk/bwsync/connect.js"
