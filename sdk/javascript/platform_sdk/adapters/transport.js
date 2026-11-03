"use strict";

/** Weg zum Adapter-Dienst: HTTP im Betrieb, feste Testdaten im Entwicklungsmodus (06 §7, §8). */

const fs = require("node:fs");
const path = require("node:path");
const { AdapterError } = require("../errors");

const FIXTURES = path.join(__dirname, "..", "fixtures");
const NO_USER = "Die Schnittstelle kann nur während einer Anfrage einer angemeldeten Person benutzt werden.";
const UNAVAILABLE = "Das System ist gerade nicht erreichbar.";
const TIMEOUT = "Das System antwortet zu langsam.";

class HttpTransport {
  constructor(baseUrl) {
    this._base = baseUrl.replace(/\/+$/, "");
  }

  async get(req, pathName, params) {
    const portal = req?.portal;
    if (!portal?.assertion) throw new AdapterError(500, "no-user-context", NO_USER);
    const headers = { Authorization: `Bearer ${portal.assertion}` };
    if (portal.requestId) headers["X-Request-Id"] = portal.requestId;
    const query = params ? `?${new URLSearchParams(params)}` : "";
    let response;
    try {
      // keine automatische Wiederholung
      response = await fetch(this._base + pathName + query, { headers, signal: AbortSignal.timeout(8000) });
    } catch (err) {
      if (err.name === "TimeoutError") throw new AdapterError(504, "backend-timeout", TIMEOUT, portal.requestId ?? null);
      throw new AdapterError(503, "backend-unavailable", UNAVAILABLE, portal.requestId ?? null);
    }
    if (response.ok) return response.json();
    throw await problem(response);
  }
}

/** Feste Testdaten aus `fixtures/<system>/<sub>.json`; unbekannte Person: leere Liste. */
class FixtureTransport {
  async get(req, pathName, params) {
    const user = req?.portal?.user;
    if (!user) throw new AdapterError(500, "no-user-context", NO_USER);
    if (pathName === "/v1/noten/me/grades") {
      const file = path.join(FIXTURES, "noten", `${user.sub}.json`);
      let data = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, "utf-8")) : { items: [] };
      if (params?.semester) data = { items: data.items.filter((g) => g.semester === params.semester) };
      return data;
    }
    throw new AdapterError(501, "not-implemented", "Diese Funktion ist hier noch nicht verfügbar.");
  }
}

async function problem(response) {
  let body = {};
  try {
    body = await response.json();
  } catch {
    body = {};
  }
  const kind = String(body.type ?? "").replace(/^urn:hka:problem:/, "") || "backend-unavailable";
  return new AdapterError(response.status, kind, body.detail || UNAVAILABLE, body.request_id ?? null);
}

module.exports = { HttpTransport, FixtureTransport, FIXTURES };
