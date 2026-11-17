"use strict";

/** Zeitpunkte für Anzeigen: Europe/Berlin, deutsches Format („16.11.2026, 14:28“). */

const FORMAT = new Intl.DateTimeFormat("de-DE", {
  timeZone: "Europe/Berlin",
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

/** `TT.MM.JJJJ, HH:MM` in Berliner Zeit; `Date` oder ISO-Text (ohne Zeitzone gilt UTC); null → `empty`. */
function formatDatetime(value, { empty = "–" } = {}) {
  if (value === null || value === undefined) return empty;
  let date = value;
  if (typeof value === "string") {
    const hasZone = /(Z|[+-]\d\d:?\d\d)$/i.test(value);
    date = new Date(hasZone ? value : `${value}Z`);
  }
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) return empty;
  const parts = Object.fromEntries(FORMAT.formatToParts(date).map((p) => [p.type, p.value]));
  return `${parts.day}.${parts.month}.${parts.year}, ${parts.hour}:${parts.minute}`;
}

module.exports = { formatDatetime };
