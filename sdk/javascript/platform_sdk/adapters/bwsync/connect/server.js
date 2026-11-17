"use strict";

const path = require("node:path");

/**
 * bwSync&Share verbinden und trennen: Server-Teil.
 *
 * Verbinden und Trennen laufen im Browser über das Gateway (gleiche Adresse wie die Seite); die App selbst ruft dafür
 * nichts auf. Ob das Konto verbunden ist, liefert `portal.adapters.bwsync.isLinked(req)`.
 */

// Routen des Gateways (Browser, fetch mit Cookie der Sitzung). Die App gibt sie nicht selbst aus; connect.js kennt sie.
const ROUTES = Object.freeze({
  status: "/connect/bwsync", // GET: {linked, account}
  start: "/connect/bwsync/start", // POST: {login_url, expires_in}
  poll: "/connect/bwsync/poll", // POST: {state: pending|linked|none, account}
  disconnect: "/connect/bwsync", // DELETE: {linked: false, revoked: true|null|false}
});

// Adresse des Browser-Skripts unter dem Pfad der App: portal.url(SCRIPT); portal.install(app) liefert es aus.
const SCRIPT = "/_sdk/bwsync/connect.js";
const SCRIPT_FILE = path.join(__dirname, "connect.js");

// Fehlertypen, die connect.js selbst meldet (window.PortalBwSync.ERRORS); sonst kommt der type des Adapters.
const POPUP_BLOCKED = "connect-popup-blocked"; // Browser hat den neuen Tab blockiert
const EXPIRED = "connect-expired"; // Anmeldung bei bwSync&Share nicht rechtzeitig abgeschlossen
const ABORTED = "connect-aborted"; // Anmeldung abgebrochen oder vom Adapter verworfen
const SESSION_EXPIRED = "portal-session-expired"; // Sitzung im Portal abgelaufen (401): Seite neu laden

module.exports = { ROUTES, SCRIPT, SCRIPT_FILE, POPUP_BLOCKED, EXPIRED, ABORTED, SESSION_EXPIRED };
