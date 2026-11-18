"use strict";

/** bwSync&Share: Datenmodelle der Adapter-Antworten. Streng: unbekannte Felder und falsche Werte sind ein Fehler. */

const { ContractError } = require("../transport");

function plain(value, what) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) throw new ContractError(what);
}

function onlyKeys(value, keys) {
  if (Object.keys(value).some((k) => !keys.has(k))) throw new ContractError("unbekanntes Feld");
}

const ENTRY_KEYS = new Set(["name", "type", "size", "modified"]);
const FOLDER_KEYS = new Set(["path", "entries", "truncated", "skipped"]);

/** Ein Eintrag eines bwSync-Ordners: `{name, type: "folder"|"file", size, modified: Date|null}`. */
function folderEntry(item) {
  plain(item, "Eintrag");
  onlyKeys(item, ENTRY_KEYS);
  const { name, type } = item;
  if (typeof name !== "string" || name.length < 1 || name.length > 255 || /[/\\]/.test(name)) {
    throw new ContractError("name");
  }
  if (type !== "folder" && type !== "file") throw new ContractError("type");
  const size = item.size ?? null;
  if (size !== null && !(Number.isInteger(size) && size >= 0)) throw new ContractError("size");
  let modified = item.modified ?? null;
  if (modified !== null) {
    if (typeof modified !== "string" || Number.isNaN(Date.parse(modified))) throw new ContractError("modified");
    modified = new Date(modified);
  }
  return Object.freeze({ name, type, size, modified });
}

/** Inhalt eines bwSync-Ordners: Ordner zuerst, dann nach Namen (sortiert der Adapter). */
function folder(data) {
  plain(data, "Ordner");
  onlyKeys(data, FOLDER_KEYS);
  if (typeof data.path !== "string" || data.path.length > 1024) throw new ContractError("path");
  if (!Array.isArray(data.entries) || data.entries.length > 1000) throw new ContractError("entries");
  if (typeof data.truncated !== "boolean") throw new ContractError("truncated"); // mehr als 1000 Einträge
  if (!(Number.isInteger(data.skipped) && data.skipped >= 0)) throw new ContractError("skipped"); // fehlende Namen
  return Object.freeze({
    path: data.path,
    entries: Object.freeze(data.entries.map(folderEntry)),
    truncated: data.truncated,
    skipped: data.skipped,
  });
}

module.exports = { folder, folderEntry };
