"use strict";

/**
 * Fehlerantworten des SDK: HTML-Seite für Browser, sonst problem+json (06 §4).
 *
 * Dazu die Standardbehandlung nicht abgefangener Fehler (sdk/README.md, „Fehler: Standard“). Ihre Texte stehen in
 * `texts.json` auf Deutsch und Englisch (HKA-101), wie auf der Fehlerseite des Portals (Ausnahme aus Regel 1).
 */

const { env } = require("./templates");
const { language, t, texts } = require("./i18n");
const { requestContext } = require("./context");
const { AdapterError } = require("./errors");
const { BACKEND_TIMEOUT, category } = require("./adapters/transport");

function error(req, res, status, title, detail, { problemType = null, requestId = null } = {}) {
  requestId = requestId ?? requestContext.getStore()?.requestId ?? null;
  if ((req.headers.accept ?? "").includes("text/html")) {
    const html = env.render("error.html", { title, detail, request_id: requestId, lang: language(req), tx: texts(req) });
    return res.status(status).type("html").send(html);
  }
  const body = { type: `urn:hka:problem:${problemType ?? status}`, title, status, detail };
  if (requestId) body.request_id = requestId;
  res.status(status);
  res.set("Content-Type", "application/problem+json");
  return res.end(JSON.stringify(body));
}

/**
 * Wie `error`, aber die HTML-Seite steht im Seitenrahmen des Portals (Kopf, Menü, Fuß, Weg zur Startseite).
 * Ohne angemeldete Person oder ohne `text/html` gilt `error`; ebenso, wenn der Rahmen nicht gebaut werden kann.
 */
async function errorInLayout(req, res, layout, status, title, detail) {
  const user = req.portal?.user;
  if (!user || !(req.headers.accept ?? "").includes("text/html")) return error(req, res, status, title, detail);
  try {
    const requestId = requestContext.getStore()?.requestId ?? null;
    const body = env.render("error_in_layout.html", {
      status,
      title,
      detail,
      request_id: requestId,
      tx: texts(req),
    });
    const html = await layout.render({ title, body, current: "", user });
    return res.status(status).type("html").send(html);
  } catch (err) {
    console.warn(`Fehlerseite im Rahmen nicht möglich, einfache Seite: ${err?.name ?? typeof err}`);
    return error(req, res, status, title, detail);
  }
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
  const title = t(`fallback_${kind}_title`, req);
  const text = t(`fallback_${kind}_text`, req);
  return error(req, res, status, title, text, { problemType, requestId });
}

module.exports = { error, errorInLayout, fallback };
