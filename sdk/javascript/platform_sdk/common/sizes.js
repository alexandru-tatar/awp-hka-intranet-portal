"use strict";

/** Dateigrößen für Anzeigen: „512 B“, „1,2 MB“ (Faktor 1024, deutsches Komma). */

/** Bytes lesbar; null (z. B. Ordner) → `empty`. */
function formatSize(size, { empty = "–" } = {}) {
  if (size === null || size === undefined) return empty;
  if (size < 1024) return `${size} B`;
  let value = size;
  let unit = "B";
  for (const next of ["KB", "MB", "GB", "TB"]) {
    value /= 1024;
    unit = next;
    if (value < 1024) break;
  }
  return `${value.toFixed(1).replace(".", ",")} ${unit}`;
}

module.exports = { formatSize };
