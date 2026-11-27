"use strict";

/**
 * Sprache und Texte des SDK (HKA-101): Seitenrahmen, Abmelde-Dialog, Fehlerseiten und Test-Anmeldung.
 *
 * Die Texte stehen in `texts.json` (in Python und JavaScript byte-gleich). Die Sprache kommt aus `Accept-Language`; das
 * Security-Gateway setzt den Header nach der Wahl der Person (Umschalter im Portal). Ohne unterstützte Sprache gilt Deutsch.
 */

const { requestContext } = require("./context");
const TEXTS = require("./texts.json");

const LANGUAGES = ["de", "en"];
const DEFAULT_LANGUAGE = "de";
const MAX_ACCEPT_LANGUAGE_LENGTH = 256;

/** Sprache aus `Accept-Language` wählen: die erste unterstützte nach Gewicht, `en-GB` zählt als `en`, sonst `de`. */
function pickLanguage(acceptLanguage) {
  if (!acceptLanguage || acceptLanguage.length > MAX_ACCEPT_LANGUAGE_LENGTH) return DEFAULT_LANGUAGE;
  const ranked = [];
  acceptLanguage.split(",").forEach((item, position) => {
    const [tag, ...params] = item.split(";").map((part) => part.trim());
    let weight = 1;
    for (const param of params) {
      const [name, ...rest] = param.split("=");
      if (name.trim().toLowerCase() === "q") {
        const value = Number(rest.join("=").trim());
        weight = rest.join("=").trim() !== "" && Number.isFinite(value) ? value : 0;
      }
    }
    const primary = tag.split("-")[0].toLowerCase();
    if (weight > 0 && LANGUAGES.includes(primary)) ranked.push([-weight, position, primary]);
  });
  ranked.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  return ranked.length ? ranked[0][2] : DEFAULT_LANGUAGE;
}

/**
 * Sprache der Ausgabe von Befehlen (ohne Anfrage): `PORTAL_LANG` ("de"/"en"), sonst `LC_ALL`, `LC_MESSAGES`, `LANG`.
 * Beginnt die erste gesetzte Variable mit "en", gilt Englisch, sonst Deutsch.
 */
function envLanguage(env = process.env) {
  const explicit = (env.PORTAL_LANG ?? "").trim().toLowerCase();
  if (LANGUAGES.includes(explicit)) return explicit;
  for (const name of ["LC_ALL", "LC_MESSAGES", "LANG"]) {
    const value = (env[name] ?? "").trim().toLowerCase();
    if (value) return value.split("_")[0].split(".")[0] === "en" ? "en" : DEFAULT_LANGUAGE;
  }
  return DEFAULT_LANGUAGE;
}

/** Sprache der laufenden Anfrage: aus dem Kontext der Middleware, sonst aus dem Header von `req`, sonst Deutsch. */
function language(req = null) {
  return requestContext.getStore()?.language ?? pickLanguage(req?.headers?.["accept-language"]);
}

/** Alle Texte der Sprache der laufenden Anfrage, für die Vorlagen (`{{ tx.logout }}`). */
function texts(req = null) {
  return TEXTS[language(req)];
}

/** Text zu einem Schlüssel in der Sprache der laufenden Anfrage. */
function t(key, req = null) {
  return TEXTS[language(req)][key];
}

module.exports = { LANGUAGES, DEFAULT_LANGUAGE, TEXTS, pickLanguage, envLanguage, language, texts, t };
