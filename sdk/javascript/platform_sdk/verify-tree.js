"use strict";

/**
 * Prüfsumme über `platform_sdk/` (06 §10), für schnelle Rückmeldung in `make lint`.
 *
 * Maßgeblich ist die Prüfung in der Pipeline gegen `sdk-releases.json` im Portal-Repository.
 * Die erwartete Summe dieser Kopie steht in `platform_sdk/SHA256` (geschrieben von `make sdk-release`).
 * Das Verfahren ist dasselbe wie in der Python-Fassung (gleiche Reihenfolge, gleiche Trennzeichen).
 *
 *     node platform_sdk/verify-tree.js    prüfen (Fehler PF-103)
 */

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const ROOT = __dirname;
const SUM_FILE_NAME = "SHA256";
const SKIP_DIRS = new Set(["__pycache__", "node_modules"]);

function listFiles(root, parts = []) {
  const found = [];
  for (const entry of fs.readdirSync(path.join(root, ...parts), { withFileTypes: true })) {
    const next = [...parts, entry.name];
    if (entry.isDirectory()) found.push(...listFiles(root, next));
    else if (entry.isFile() && entry.name !== SUM_FILE_NAME && !next.some((p) => SKIP_DIRS.has(p))) found.push(next);
  }
  return found;
}

/** Wie Python: Pfade nach ihren Teilen sortieren, nicht nach dem ganzen Text. */
function comparePaths(a, b) {
  for (let i = 0; i < Math.min(a.length, b.length); i += 1) {
    if (a[i] !== b[i]) return a[i] < b[i] ? -1 : 1;
  }
  return a.length - b.length;
}

/** SHA-256 über die sortierte Liste (relativer Pfad, Inhalt) aller Dateien außer `SHA256`. */
function treeHash(root = ROOT) {
  const digest = crypto.createHash("sha256");
  for (const parts of listFiles(root).sort(comparePaths)) {
    digest.update(Buffer.concat([Buffer.from(parts.join("/")), Buffer.from([0])]));
    digest.update(Buffer.concat([fs.readFileSync(path.join(root, ...parts)), Buffer.from([0])]));
  }
  return `sha256:${digest.digest("hex")}`;
}

function main() {
  const sumFile = path.join(ROOT, SUM_FILE_NAME);
  const expected = fs.existsSync(sumFile) ? fs.readFileSync(sumFile, "utf-8").trim() : "";
  if (treeHash() === expected) return 0;
  console.error(
    "FEHLER PF-103  –  Portal-Bibliothek verändert\n" +
      "Was tun: Änderungen in platform_sdk/ zurücknehmen oder `make sdk-update` ausführen.",
  );
  return 1;
}

if (require.main === module) process.exit(main());

module.exports = { treeHash, ROOT, SUM_FILE_NAME };
