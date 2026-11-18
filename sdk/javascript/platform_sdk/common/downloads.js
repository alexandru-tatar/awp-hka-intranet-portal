"use strict";

/** Downloads: sicherer Content-Disposition-Header und Schutz-Header. */

// Für jede Antwort mit Dateiinhalt: Browser rät keinen Typ, nichts wird zwischengespeichert.
const DOWNLOAD_HEADERS = Object.freeze({ "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store" });

const NOT_PRINTABLE = /[\p{C}\p{Zl}\p{Zp}\p{Zs}]/u; // wie Pythons str.isprintable(), Leerzeichen erlaubt

/** wie Pythons urllib.parse.quote(text, safe="") */
function quote(text) {
  return encodeURIComponent(text).replace(/[!'()*]/g, (c) => `%${c.charCodeAt(0).toString(16).toUpperCase()}`);
}

/**
 * `attachment` mit ASCII-Ersatzname (`filename`) und vollem Namen UTF-8-kodiert (`filename*`).
 * Anführungszeichen, Backslash und Steuerzeichen werden entfernt; leer → `download`.
 */
function contentDisposition(filename) {
  const clean = [...String(filename)].filter((c) => (c === " " || !NOT_PRINTABLE.test(c)) && c !== '"' && c !== "\\")
    .join("").trim() || "download";
  let ascii = clean.normalize("NFKD").replace(/[^\x00-\x7f]/g, "").trim();
  const dot = ascii.lastIndexOf(".");
  if (!ascii || (dot >= 0 && !ascii.slice(0, dot).trim())) {
    ascii = `download${dot >= 0 ? ascii.slice(dot) : ""}`; // z. B. „日本.txt“ -> „download.txt“
  }
  return `attachment; filename="${ascii}"; filename*=UTF-8''${quote(clean)}`;
}

/** `Content-Disposition` plus `DOWNLOAD_HEADERS`. */
function downloadHeaders(filename) {
  return { "Content-Disposition": contentDisposition(filename), ...DOWNLOAD_HEADERS };
}

module.exports = { DOWNLOAD_HEADERS, contentDisposition, downloadHeaders };
