"use strict";

/**
 * Fehlerantworten des SDK: HTML-Seite für Browser, sonst problem+json (06 §4).
 *
 * Dazu die Standardbehandlung nicht abgefangener Fehler (sdk/README.md, „Fehler: Standard“). Ihre Texte stehen nur
 * hier, auf der Fehlerseite des Portals (Ausnahme aus Regel 1).
 */

const { env } = require("./templates");
const { requestContext } = require("./context");
const { AdapterError } = require("./errors");
const { BACKEND_TIMEOUT, category } = require("./adapters/transport");

// Titel und Text je Art (domain = fachlich, technical = technisch, call = Aufruf oder Programmierfehler).
// "request" (Fehler mit 4xx-Status, z. B. ungültiges JSON von Express) nutzt den allgemeinen Text von "domain".
const FALLBACK_TEXTS = {
  domain: [
    "Das hat nicht geklappt",
    "Die Aktion war nicht möglich. Bitte gehen Sie zurück, laden Sie die Seite neu und versuchen Sie es erneut.",
  ],
  technical: ["Gerade nicht erreichbar", "Der Dienst ist gerade nicht erreichbar. Bitte versuchen Sie es später erneut."],
  call: [
    "Fehler in der Anwendung",
    "In dieser Anwendung ist ein Fehler aufgetreten. Wenn das wieder passiert, nennen Sie bitte die Vorgangsnummer.",
  ],
};

function error(req, res, status, title, detail, { problemType = null, requestId = null } = {}) {
  requestId = requestId ?? requestContext.getStore()?.requestId ?? null;
  if ((req.headers.accept ?? "").includes("text/html")) {
    const html = env.render("error.html", { title, detail, request_id: requestId });
    return res.status(status).type("html").send(html);
  }
  const body = { type: `urn:hka:problem:${problemType ?? status}`, title, status, detail };
  if (requestId) body.request_id = requestId;
  res.status(status);
  res.set("Content-Type", "application/problem+json");
  return res.end(JSON.stringify(body));
}

/** 4xx-Status eines anderen Fehlers (Express/body-parser: err.status oder err.statusCode), sonst null. */
function clientStatus(err) {
  const status = Number(err?.status ?? err?.statusCode);
  return Number.isInteger(status) && status >= 400 && status < 500 ? status : null;
}

/**
 * Antwort auf einen Fehler, den die App nicht abgefangen hat. Details nur ins Log, nie in die Antwort.
 * Andere Fehler mit 4xx-Status behalten ihren Status (wie bei FastAPI); nur Fehler ohne Status werden 500.
 */
function fallback(err, req, res) {
  const requestId = req.portal?.requestId ?? req.headers["x-request-id"] ?? null;
  const entry = { path: req.path };
  let kind;
  let status;
  let problemType = null;
  if (err instanceof AdapterError) {
    kind = category(err);
    if (kind === "technical") status = err.type === BACKEND_TIMEOUT ? 504 : 503;
    else if (kind === "domain") status = err.status >= 400 && err.status < 500 ? err.status : 500;
    else status = 500;
    Object.assign(entry, { category: kind, type: err.type, status: err.status });
    if (kind === "domain") entry.hint = "Die App behandelt diesen type nicht selbst.";
    if (kind === "call") entry.detail = err.detail;
    problemType = err.type;
  } else if (clientStatus(err) !== null) {
    kind = "domain";
    status = clientStatus(err);
    Object.assign(entry, { category: "request", error: err?.name ?? typeof err, status });
  } else {
    kind = "call";
    status = 500;
    Object.assign(entry, { category: "other", error: err?.name ?? typeof err, stack: err?.stack ?? String(err) });
  }
  const level = kind === "domain" || kind === "technical" ? "warning" : "error";
  console.log(
    JSON.stringify({
      ts: new Date().toISOString().replace(/\.\d+Z$/, "Z"),
      level,
      event: "unhandled-error",
      request_id: requestId,
      ...entry,
    }),
  );
  const [title, text] = FALLBACK_TEXTS[kind];
  return error(req, res, status, title, text, { problemType, requestId });
}

module.exports = { FALLBACK_TEXTS, error, fallback };
