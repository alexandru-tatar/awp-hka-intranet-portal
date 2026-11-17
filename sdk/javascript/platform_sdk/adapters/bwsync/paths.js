"use strict";

/**
 * bwSync&Share: Regeln für Namen und Pfade, wie der Adapter sie durchsetzt, und Daten für Anzeigen.
 *
 * Pfade sind relativ zur Wurzel des Kontos (`"Studium/plan.pdf"`); `""` ist die Wurzel. Kein HTML, keine Texte.
 */

const MAX_NAME = 255; // Zeichen je Name
const MAX_PATH = 1024; // Zeichen je Pfad
const FORBIDDEN_CHARS = "/\\:%?#"; // in Namen nicht erlaubt (kann der Adapter nicht verarbeiten)

const NOT_PRINTABLE = /[\p{C}\p{Zl}\p{Zp}\p{Zs}]/u; // wie Pythons str.isprintable(), Leerzeichen erlaubt

function printable(char) {
  return char === " " || !NOT_PRINTABLE.test(char);
}

/** Ein Name (Datei oder Ordner): 1–255 Zeichen, ohne `FORBIDDEN_CHARS`, Steuerzeichen und Leerraum außen. */
function validName(name) {
  return (
    typeof name === "string" &&
    name.length > 0 &&
    [...name].length <= MAX_NAME &&
    name !== "." &&
    name !== ".." &&
    name === name.trim() &&
    ![...name].some((c) => FORBIDDEN_CHARS.includes(c) || !printable(c))
  );
}

/** Nur der letzte Teil eines Namens (z. B. aus einem Upload), ohne Pfad und Steuerzeichen; danach `validName`. */
function cleanName(raw) {
  const parts = String(raw ?? "").replace(/\\/g, "/").split("/").filter((p) => p !== "" && p !== ".");
  const name = parts.length ? parts[parts.length - 1] : "";
  return [...name].filter(printable).join("").trim();
}

/** Relativer Pfad aus gültigen Namen; `""` (Wurzel) nur mit `root: true` (Vorgabe). */
function validPath(pathName, { root = true } = {}) {
  if (pathName === "") return root;
  return typeof pathName === "string" && [...pathName].length <= MAX_PATH && pathName.split("/").every(validName);
}

function join(folder, name) {
  return folder ? `${folder}/${name}` : name;
}

function parentOf(pathName) {
  const i = pathName.lastIndexOf("/");
  return i < 0 ? "" : pathName.slice(0, i);
}

function nameOf(pathName) {
  return pathName.slice(pathName.lastIndexOf("/") + 1);
}

/** Teile des Pfads für eine Pfadleiste, ohne Wurzel: `"a/b"` → `[{name: a, path: a}, {name: b, path: a/b}]`. */
function breadcrumbs(pathName) {
  const items = [];
  let soFar = "";
  for (const part of pathName ? pathName.split("/") : []) {
    soFar = join(soFar, part);
    items.push({ name: part, path: soFar });
  }
  return items;
}

module.exports = {
  MAX_NAME, MAX_PATH, FORBIDDEN_CHARS, validName, cleanName, validPath, join, parentOf, nameOf, breadcrumbs,
};
