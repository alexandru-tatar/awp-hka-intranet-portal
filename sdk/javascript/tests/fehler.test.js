"use strict";

/** Fehler-Standard: Arten, 504 ohne type, Standardbehandlung nicht abgefangener Fehler (sdk/README.md). */

const assert = require("node:assert/strict");
const express = require("express");
const { after, before, beforeEach, test } = require("node:test");
const { AdapterError } = require("../platform_sdk");
const transport = require("../platform_sdk/adapters/transport");
const errors = require("../platform_sdk/adapters/bwsync/errors");
const { makePortal, makeToken, serve } = require("./helpers");

test("Arten", () => {
  assert.equal(transport.category(new AdapterError(503, transport.BACKEND_UNAVAILABLE, "")), "technical");
  assert.equal(transport.category(new AdapterError(504, transport.BACKEND_TIMEOUT, "")), "technical");
  assert.equal(transport.category(new AdapterError(502, transport.CONTRACT_VIOLATION, "")), "technical");
  for (const kind of [transport.NO_USER_CONTEXT, transport.NOT_IMPLEMENTED, transport.DOWNLOAD_TOO_LARGE,
    transport.SCOPE_NOT_GRANTED]) {
    assert.equal(transport.category(new AdapterError(500, kind, "")), "call");
  }
  assert.equal(transport.category(new AdapterError(423, errors.LOCKED, "")), "domain");
  assert.equal(transport.category(new AdapterError(409, "unbekannt-neu", "")), "domain");
});

test("Antwort ohne type: 504 heißt backend-timeout, sonst backend-unavailable", async () => {
  const cases = [
    [504, "", transport.BACKEND_TIMEOUT],
    [502, "", transport.BACKEND_UNAVAILABLE],
    [400, '{"detail": "x"}', transport.BACKEND_UNAVAILABLE],
    [500, "[1, 2]", transport.BACKEND_UNAVAILABLE],
    [504, '{"type": "urn:hka:problem:bwsync-locked"}', errors.LOCKED],
  ];
  for (const [status, body, kind] of cases) {
    const server = await serve(express().use((_req, res) => res.status(status).send(body)));
    try {
      const req = { portal: { assertion: makeToken(), requestId: null } };
      await assert.rejects(new transport.HttpTransport(server.base).get(req, "/x", null), (err) => {
        assert.deepEqual([err.status, err.type], [status, kind]);
        return true;
      });
    } finally {
      await server.close();
    }
  }
});

const ERRORS = {
  fachlich: () => new AdapterError(423, errors.LOCKED, "geheimes detail"),
  technisch: () => new AdapterError(503, transport.BACKEND_UNAVAILABLE, ""),
  zeit: () => new AdapterError(504, transport.BACKEND_TIMEOUT, ""),
  aufruf: () => new AdapterError(500, transport.NO_USER_CONTEXT, "geheimes detail"),
  recht: () => new AdapterError(403, transport.SCOPE_NOT_GRANTED, "geheimes detail"),
};

let server;
let lines = [];
const realLog = console.log;
before(async () => {
  const portal = makePortal();
  const app = express();
  portal.install(app);
  const router = portal.router();
  router.get("/fehler/:art", async (req) => {
    if (req.params.art === "anderer") throw new Error("geheimer Text aus dem Stack");
    throw ERRORS[req.params.art]();
  });
  router.get("/abgefangen", async (_req, res) => {
    try {
      throw ERRORS.fachlich();
    } catch {
      res.type("html").send("<h1>Eigener Text der App</h1>");
    }
  });
  app.use(portal.url("/"), router);
  portal.handleErrors(app);
  server = await serve(app);
  console.log = (line) => {
    try {
      const entry = JSON.parse(line);
      if (entry.event === "unhandled-error") return lines.push(entry);
    } catch {
      // keine JSON-Zeile
    }
    return realLog(line);
  };
});
after(async () => {
  console.log = realLog;
  await server.close();
});
beforeEach(() => {
  lines = [];
});

const get = (path, accept = "text/html") =>
  fetch(`${server.base}${path}`, { headers: { "X-Portal-Assertion": makeToken(), "X-Request-Id": "req-123", Accept: accept } });

for (const [art, status, title, text] of [
  ["fachlich", 423, "Das hat nicht geklappt", "Die Aktion war nicht möglich."],
  ["technisch", 503, "Gerade nicht erreichbar", "später erneut"],
  ["zeit", 504, "Gerade nicht erreichbar", "später erneut"],
  ["aufruf", 500, "Fehler in der Anwendung", "nennen Sie bitte die Vorgangsnummer"],
  ["recht", 500, "Fehler in der Anwendung", "nennen Sie bitte die Vorgangsnummer"],
  ["anderer", 500, "Fehler in der Anwendung", "nennen Sie bitte die Vorgangsnummer"],
]) {
  test(`Fallback als HTML: ${art}`, async () => {
    const response = await get(`/fehler/${art}`);
    assert.equal(response.status, status);
    const html = await response.text();
    assert.ok(html.includes('<html lang="de">') && html.includes(`<h1>${title}</h1>`) && html.includes(text), html);
    assert.ok(html.includes("Vorgangsnummer: req-123"));
    assert.ok(!html.includes("geheim") && !html.includes("Error:") && !/\n\s+at \S/.test(html), html);
    assert.equal(lines.length, 1);
    assert.equal(lines[0].request_id, "req-123");
    assert.equal(lines[0].level, ["fachlich", "technisch", "zeit"].includes(art) ? "warning" : "error");
  });
}

test("Fallback als JSON behält den type", async () => {
  const response = await get("/fehler/fachlich", "application/json");
  assert.equal(response.status, 423);
  assert.equal(response.headers.get("content-type"), "application/problem+json");
  const body = await response.json();
  assert.equal(body.type, "urn:hka:problem:bwsync-locked");
  assert.equal(body.request_id, "req-123");
  assert.ok(!JSON.stringify(body).includes("geheim"));
});

test("Fallback als JSON bei anderem Fehler", async () => {
  const response = await get("/fehler/anderer", "application/json");
  const text = await response.text();
  assert.equal(response.status, 500);
  assert.equal(JSON.parse(text).type, "urn:hka:problem:500");
  assert.ok(!text.includes("geheim") && !text.includes("stack"));
});

test("Details nur im Log", async () => {
  await get("/fehler/aufruf");
  await get("/fehler/anderer");
  await get("/fehler/fachlich");
  const [aufruf, anderer, fachlich] = lines;
  assert.equal(aufruf.detail, "geheimes detail");
  assert.equal(anderer.category, "other");
  assert.ok(anderer.stack.includes("geheimer Text aus dem Stack"));
  assert.ok(!("detail" in fachlich) && "hint" in fachlich);
});

test("App fängt selbst ab: kein Fallback", async () => {
  const response = await get("/abgefangen");
  assert.equal(response.status, 200);
  assert.match(await response.text(), /Eigener Text der App/);
  assert.equal(lines.length, 0);
});
