"use strict";

/** bwSync&Share: alle Aufrufe des bwSync-Adapters (Beschreibung: README.md in diesem Ordner). */

const { AdapterError } = require("../../errors");
const { CONTRACT_VIOLATION, ContractError } = require("../transport");
const { folder } = require("./models");

/** wie Pythons urllib.parse.quote(path, safe="/") */
function quote(pathName) {
  return pathName
    .split("/")
    .map((part) => encodeURIComponent(part).replace(/[!'()*]/g, (c) => `%${c.charCodeAt(0).toString(16).toUpperCase()}`))
    .join("/");
}

/**
 * Dateien und Ordner im bwSync&Share-Konto der angemeldeten Person (über den bwSync-Adapter).
 *
 * Pfade sind relativ zur Wurzel des Kontos, z. B. `"Studium/Notizen.pdf"`; `""` ist die Wurzel (nur bei `list`).
 * Fehler kommen als `AdapterError`; `type` nennt den Fall (Konstanten in `./errors`).
 */
class BwSyncClient {
  constructor(transport) {
    this._t = transport;
  }

  static _rel(pathName) {
    if (
      typeof pathName !== "string" ||
      !pathName ||
      [...pathName].length > 1024 ||
      /[\\%?#:]/.test(pathName) ||
      [...pathName].some((c) => c.codePointAt(0) < 32 || c.codePointAt(0) === 127) ||
      pathName.split("/").some((part) => part === "" || part === "." || part === ".." || [...part].length > 255)
    ) {
      throw new TypeError("Ein relativer Dateipfad ohne Traversal ist erforderlich.");
    }
    return pathName;
  }

  static _path(pathName) {
    return `/bwsync/files/${quote(BwSyncClient._rel(pathName))}`;
  }

  static _folder(pathName, { root = false } = {}) {
    if (root && pathName === "") return "/bwsync/folders/";
    return `/bwsync/folders/${quote(BwSyncClient._rel(pathName))}`;
  }

  /** Neue Datei anlegen (überschreibt nie: vorhanden → AdapterError 412). `data`: Buffer/Uint8Array. */
  async upload(req, pathName, data) {
    await this._t.putBytes(req, BwSyncClient._path(pathName), data);
  }

  async download(req, pathName, { maxBytes = 10_000_000 } = {}) {
    return this._t.getBytes(req, BwSyncClient._path(pathName), { maxBytes });
  }

  /**
   * Ordner als ZIP, gestreamt (Scope `bwsync:read`); nicht die Wurzel (`""`).
   *
   *   const stream = await portal.adapters.bwsync.downloadZip(req, "Studium"); // Fehler hier, vor der Antwort
   *   res.set({ "Content-Type": "application/zip", ...downloadHeaders("Studium.zip") }); // common/downloads
   *   stream.readable().pipe(res);
   */
  async downloadZip(req, pathName) {
    return this._t.openStream(req, `/bwsync/zip/${quote(BwSyncClient._rel(pathName))}`);
  }

  /** Ist das bwSync&Share-Konto der Person verbunden? (Scope `bwsync:read`; ohne Kontonamen) */
  async isLinked(req) {
    const data = await this._t.get(req, "/bwsync/link", null);
    if (data === null || typeof data !== "object" || typeof data.linked !== "boolean") {
      throw new AdapterError(502, CONTRACT_VIOLATION, "");
    }
    return data.linked;
  }

  /** Direkte Einträge eines Ordners (Scope `bwsync:read`). */
  async list(req, pathName = "") {
    const data = await this._t.get(req, BwSyncClient._folder(pathName, { root: true }), null);
    try {
      return folder(data);
    } catch (err) {
      if (err instanceof ContractError) throw new AdapterError(502, CONTRACT_VIOLATION, "");
      throw err;
    }
  }

  /** Ordner anlegen (Scope `bwsync:write`); vorhanden → `bwsync-exists`. */
  async mkdir(req, pathName) {
    await this._t.send(req, "POST", BwSyncClient._folder(pathName));
  }

  /** Verschieben oder umbenennen, nie überschreiben (Scope `bwsync:write`); Ziel vorhanden → `bwsync-exists`. */
  async move(req, source, target) {
    await this._t.send(req, "POST", "/bwsync/move", { from: BwSyncClient._rel(source), to: BwSyncClient._rel(target) });
  }

  /** Datei löschen, mit `{ folder: true }` einen Ordner samt Inhalt (Scope `bwsync:delete`). Nie die Wurzel. */
  async delete(req, pathName, { folder: isFolder = false } = {}) {
    await this._t.send(req, "DELETE", isFolder ? BwSyncClient._folder(pathName) : BwSyncClient._path(pathName));
  }
}

module.exports = { BwSyncClient };
