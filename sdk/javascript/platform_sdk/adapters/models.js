"use strict";

/**
 * Datenmodelle nach den OpenAPI-Dateien des Adapter-Dienstes (05 §4).
 * Streng: unbekannte Felder und falsche Werte sind ein Fehler (`ContractError`).
 */

class ContractError extends Error {}

const GRADE_RE = /^([1-4][,.][037]|5[,.]0|bestanden|nicht bestanden)$/;

function grade(item) {
  const allowed = new Set(["module", "semester", "grade", "credits"]);
  if (item === null || typeof item !== "object" || Array.isArray(item)) throw new ContractError("Note");
  if (Object.keys(item).some((k) => !allowed.has(k))) throw new ContractError("unbekanntes Feld");
  if (typeof item.module !== "string" || item.module.length > 120) throw new ContractError("module");
  if (typeof item.semester !== "string") throw new ContractError("semester");
  if (typeof item.grade !== "string" || !GRADE_RE.test(item.grade)) throw new ContractError("grade");
  const credits = item.credits ?? null;
  if (credits !== null && !(Number.isInteger(credits) && credits >= 0 && credits <= 30)) {
    throw new ContractError("credits");
  }
  return Object.freeze({ module: item.module, semester: item.semester, grade: item.grade, credits });
}

function gradeList(data) {
  if (data === null || typeof data !== "object" || Array.isArray(data)) throw new ContractError("Liste");
  if (Object.keys(data).some((k) => k !== "items")) throw new ContractError("unbekanntes Feld");
  if (!Array.isArray(data.items) || data.items.length > 500) throw new ContractError("items");
  return Object.freeze({ items: Object.freeze(data.items.map(grade)) });
}

module.exports = { ContractError, gradeList };
