"use strict";

/** Fehlerantworten des SDK: HTML-Seite für Browser, sonst problem+json (06 §4). */

const { env } = require("./templates");
const { requestContext } = require("./context");

function error(req, res, status, title, detail) {
  const requestId = requestContext.getStore()?.requestId ?? null;
  if ((req.headers.accept ?? "").includes("text/html")) {
    const html = env.render("error.html", { title, detail, request_id: requestId });
    return res.status(status).type("html").send(html);
  }
  const body = { type: `urn:hka:problem:${status}`, title, status, detail };
  if (requestId) body.request_id = requestId;
  res.status(status);
  res.set("Content-Type", "application/problem+json");
  return res.end(JSON.stringify(body));
}

module.exports = { error };
