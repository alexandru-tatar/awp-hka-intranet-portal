"use strict";

/**
 * bwSync&Share: Fehlertypen (`AdapterError.type`).
 *
 * Nur Konstanten. Bedeutung und typische Reaktion stehen in `README.md` (Abschnitt „Fehler“); allgemeine Typen
 * (`backend-unavailable` usw.) in `adapters/transport`.
 */

const NOT_LINKED = "bwsync-not-linked"; // 403: Konto ist nicht verbunden
const LINK_INVALID = "bwsync-link-invalid"; // 403: Verbindung gilt nicht mehr (App-Passwort widerrufen, Zugang nicht lesbar)
const FORBIDDEN = "bwsync-forbidden"; // 403: bwSync&Share verweigert genau diese Aktion
const NOT_FOUND = "bwsync-not-found"; // 404
const EXISTS = "bwsync-exists"; // 409/412: Ziel gibt es schon (nie überschrieben)
const PARENT_MISSING = "bwsync-parent-missing"; // 409: Elternordner fehlt
const CONFLICT = "bwsync-conflict"; // 409: sonstiger Konflikt in bwSync&Share
const TOO_LARGE = "bwsync-too-large"; // 413: Upload größer als die Grenze des Adapters (10 MB)
const LOCKED = "bwsync-locked"; // 423: in bwSync&Share gesperrt (z. B. dort geöffnet)
const NOT_A_FILE = "bwsync-not-a-file"; // 409: Datei erwartet, es ist ein Ordner (z. B. Datei löschen)
const NOT_A_FOLDER = "bwsync-not-a-folder"; // 409: Ordner erwartet, es ist eine Datei (auflisten, Ordner löschen)
const MOVE_INTO_SELF = "bwsync-move-into-self"; // 400: Ziel ist die Quelle selbst oder ein Ordner in ihr
const FOLDER_TOO_LARGE = "bwsync-folder-too-large"; // 422: Ordnerliste größer als die Grenze des Adapters
const LINK_FAILED = "bwsync-link-failed"; // 403: beim Verbinden kam ein Zugang, den bwSync&Share gleich ablehnt (connect.js)

const LINK_PROBLEMS = Object.freeze(new Set([NOT_LINKED, LINK_INVALID])); // die Person muss (neu) verbinden

module.exports = {
  NOT_LINKED, LINK_INVALID, FORBIDDEN, NOT_FOUND, EXISTS, PARENT_MISSING, CONFLICT, TOO_LARGE, LOCKED,
  NOT_A_FILE, NOT_A_FOLDER, MOVE_INTO_SELF, FOLDER_TOO_LARGE, LINK_FAILED, LINK_PROBLEMS,
};
