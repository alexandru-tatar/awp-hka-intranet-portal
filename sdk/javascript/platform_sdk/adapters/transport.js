"use strict";

/** Weg zum Adapter-Dienst: HTTP im Betrieb, feste Testdaten im Entwicklungsmodus (06 §7, §8). */

const fs = require("node:fs");
const path = require("node:path");
const { Readable } = require("node:stream");
const { AdapterError } = require("../errors");

const ADAPTERS = __dirname; // Testdaten: adapters/<system>/fixtures/<sub>.json
// Allgemeine Fehlertypen (für alle Systeme). Bedeutung und typische Reaktion: sdk/README.md und die README je System.
const BACKEND_UNAVAILABLE = "backend-unavailable"; // Adapter nicht erreichbar oder Antwort ohne eigenen type
const BACKEND_TIMEOUT = "backend-timeout"; // Adapter antwortet nicht rechtzeitig
const CONTRACT_VIOLATION = "contract-violation"; // Antwort passt nicht zur Beschreibung
const NOT_IMPLEMENTED = "not-implemented"; // im Entwicklungsmodus (Testdaten) nicht verfügbar
const NO_USER_CONTEXT = "no-user-context"; // Aufruf außerhalb einer Anfrage einer angemeldeten Person (Programmierfehler)
const DOWNLOAD_TOO_LARGE = "download-too-large"; // Download größer als maxBytes (Grenze der App)
const SCOPE_NOT_GRANTED = "scope-not-granted"; // der App fehlt das Recht im Manifest (Plattform-Prüfung im Adapter)

// Arten (sdk/README.md, „Fehler: Standard“). Jeder andere type ist fachlich, auch ein unbekannter.
const TECHNICAL_TYPES = Object.freeze(new Set([BACKEND_UNAVAILABLE, BACKEND_TIMEOUT, CONTRACT_VIOLATION]));
const CALL_TYPES = Object.freeze(new Set([NO_USER_CONTEXT, NOT_IMPLEMENTED, DOWNLOAD_TOO_LARGE, SCOPE_NOT_GRANTED]));

/** Art eines Fehlers: "technical", "call" oder "domain" (fachlich). */
function category(err) {
  if (TECHNICAL_TYPES.has(err.type)) return "technical";
  if (CALL_TYPES.has(err.type)) return "call";
  return "domain";
}

// detail nur für Logs (Regel 4 in sdk/README.md); ohne Antwort vom Adapter bleibt detail leer.
/** Antwort passt nicht zum Modell (intern; nach außen AdapterError mit CONTRACT_VIOLATION). */
class ContractError extends Error {}

const _NO_USER = "Aufruf außerhalb einer Anfrage einer angemeldeten Person.";
const _DEV_ONLY = "Im Entwicklungsmodus ohne Adapter nicht verfügbar (Gateway-Testbetrieb nötig).";

/**
 * Antwortinhalt des Adapters zum Durchreichen, ohne ihn ganz zu laden. Fehler des Adapters kommen schon beim Öffnen.
 * `for await (const chunk of stream)` oder `stream.readable().pipe(res)`. Bricht die App vorher ab: `stream.close()`
 * (mehrfach schadet nicht).
 */
class AdapterStream {
  constructor(response, controller) {
    this._response = response;
    this._controller = controller;
    this.closed = false;
  }

  async *[Symbol.asyncIterator]() {
    try {
      for await (const chunk of this._response.body ?? []) yield Buffer.from(chunk);
    } finally {
      await this.close();
    }
  }

  /** Node-Stream, z. B. `stream.readable().pipe(res)`; schließt beim Abbruch der Antwort mit. */
  readable() {
    const readable = Readable.from(this);
    readable.on("close", () => this.close());
    return readable;
  }

  async close() {
    if (this.closed) return;
    this.closed = true;
    try {
      await this._response.body?.cancel();
    } catch {
      // schon gelesen oder abgebrochen
    }
    this._controller.abort();
  }
}

function context(req) {
  const portal = req?.portal;
  if (!portal?.assertion) throw new AdapterError(500, NO_USER_CONTEXT, _NO_USER);
  const headers = { Authorization: `Bearer ${portal.assertion}` };
  if (portal.requestId) headers["X-Request-Id"] = portal.requestId;
  return { headers, requestId: portal.requestId ?? null };
}

class HttpTransport {
  constructor(baseUrl) {
    this._base = baseUrl.replace(/\/+$/, "");
  }

  /** fetch ohne Weiterleitung und ohne Wiederholung; Netz- und Zeitfehler als AdapterError. */
  async _fetch(url, init, ms, requestId) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(new DOMException("timeout", "TimeoutError")), ms);
    try {
      const response = await fetch(url, { ...init, redirect: "manual", signal: controller.signal });
      return { response, controller, timer };
    } catch (err) {
      clearTimeout(timer);
      if (err?.name === "TimeoutError" || controller.signal.reason?.name === "TimeoutError") {
        throw new AdapterError(504, BACKEND_TIMEOUT, "", requestId);
      }
      throw new AdapterError(503, BACKEND_UNAVAILABLE, "", requestId);
    }
  }

  async get(req, pathName, params) {
    const { headers, requestId } = context(req);
    const query = params ? `?${new URLSearchParams(params)}` : "";
    const { response, timer } = await this._fetch(this._base + pathName + query, { headers }, 8000, requestId);
    try {
      if (!response.ok) throw await problem(response);
      try {
        return await response.json();
      } catch (err) {
        if (err?.name === "TimeoutError") throw new AdapterError(504, BACKEND_TIMEOUT, "", requestId);
        throw new AdapterError(502, CONTRACT_VIOLATION, "", requestId);
      }
    } finally {
      clearTimeout(timer);
    }
  }

  /** POST/DELETE ohne Antwortinhalt (201 oder 204), z. B. Ordner anlegen, verschieben, löschen. */
  async send(req, method, pathName, body = null) {
    const { headers, requestId } = context(req);
    const init = { method, headers };
    if (body !== null && body !== undefined) {
      init.headers = { ...headers, "Content-Type": "application/json" };
      init.body = JSON.stringify(body);
    }
    const { response, timer } = await this._fetch(this._base + pathName, init, 30000, requestId);
    try {
      if (!response.ok) throw await problem(response);
      await response.body?.cancel();
      if (response.status !== 201 && response.status !== 204) {
        throw new AdapterError(502, CONTRACT_VIOLATION, "", requestId);
      }
    } finally {
      clearTimeout(timer);
    }
  }

  async putBytes(req, pathName, data) {
    const { headers, requestId } = context(req);
    const init = { method: "PUT", headers: { ...headers, "Content-Type": "application/octet-stream" }, body: data };
    const { response, timer } = await this._fetch(this._base + pathName, init, 30000, requestId);
    try {
      if (!response.ok) throw await problem(response);
      await response.body?.cancel();
      if (response.status !== 204) throw new AdapterError(502, CONTRACT_VIOLATION, "", requestId);
    } finally {
      clearTimeout(timer);
    }
  }

  async getBytes(req, pathName, { maxBytes }) {
    if (!(maxBytes >= 0)) throw new RangeError("maxBytes muss nichtnegativ sein.");
    const { headers, requestId } = context(req);
    const { response, controller, timer } = await this._fetch(this._base + pathName, { headers }, 30000, requestId);
    try {
      if (!response.ok) throw await problem(response);
      if (response.status !== 200) {
        await response.body?.cancel();
        throw new AdapterError(502, CONTRACT_VIOLATION, "", requestId);
      }
      const parts = [];
      let size = 0;
      try {
        for await (const chunk of response.body ?? []) {
          size += chunk.length;
          if (size > maxBytes) {
            controller.abort();
            throw new AdapterError(413, DOWNLOAD_TOO_LARGE, `mehr als maxBytes=${maxBytes}`, requestId);
          }
          parts.push(Buffer.from(chunk));
        }
      } catch (err) {
        if (err instanceof AdapterError) throw err;
        if (controller.signal.reason?.name === "TimeoutError") throw new AdapterError(504, BACKEND_TIMEOUT, "", requestId);
        throw new AdapterError(503, BACKEND_UNAVAILABLE, "", requestId);
      }
      return Buffer.concat(parts);
    } finally {
      clearTimeout(timer);
    }
  }

  /** GET mit gestreamter Antwort (200), z. B. ZIP eines Ordners. Ohne Obergrenze; 60 s bis zur Antwort. */
  async openStream(req, pathName) {
    const { headers, requestId } = context(req);
    const { response, controller, timer } = await this._fetch(this._base + pathName, { headers }, 60000, requestId);
    clearTimeout(timer);
    if (response.status !== 200) {
      const error = response.ok ? new AdapterError(502, CONTRACT_VIOLATION, "", requestId) : await problem(response);
      controller.abort();
      throw error;
    }
    return new AdapterStream(response, controller);
  }
}

/** Feste Testdaten aus `adapters/<system>/fixtures/<sub>.json`; unbekannte Person: leere Liste. */
class FixtureTransport {
  async get(req, pathName, params) {
    if (pathName.startsWith("/bwsync/")) throw new AdapterError(501, NOT_IMPLEMENTED, _DEV_ONLY);
    const user = req?.portal?.user;
    if (!user) throw new AdapterError(500, NO_USER_CONTEXT, _NO_USER);
    if (pathName === "/v1/noten/me/grades") {
      const file = path.join(ADAPTERS, "noten", "fixtures", `${user.sub}.json`);
      let data = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, "utf-8")) : { items: [] };
      if (params?.semester) data = { items: data.items.filter((g) => g.semester === params.semester) };
      return data;
    }
    throw new AdapterError(501, NOT_IMPLEMENTED, _DEV_ONLY);
  }

  async send() {
    throw new AdapterError(501, NOT_IMPLEMENTED, _DEV_ONLY);
  }

  async putBytes() {
    throw new AdapterError(501, NOT_IMPLEMENTED, _DEV_ONLY);
  }

  async getBytes() {
    throw new AdapterError(501, NOT_IMPLEMENTED, _DEV_ONLY);
  }

  async openStream() {
    throw new AdapterError(501, NOT_IMPLEMENTED, _DEV_ONLY);
  }
}

async function problem(response) {
  let body = {};
  try {
    body = await response.json();
  } catch {
    body = {};
  }
  if (body === null || typeof body !== "object") body = {};
  // Ohne type: technisch. 504 heißt Zeitüberschreitung (auch zwischen Adapter und Fachsystem).
  const fallback = response.status === 504 ? BACKEND_TIMEOUT : BACKEND_UNAVAILABLE;
  const kind = String(body.type ?? "").replace(/^urn:hka:problem:/, "") || fallback;
  return new AdapterError(response.status, kind, String(body.detail || ""), body.request_id ?? null);
}

module.exports = {
  ADAPTERS,
  AdapterStream,
  BACKEND_TIMEOUT,
  BACKEND_UNAVAILABLE,
  CALL_TYPES,
  CONTRACT_VIOLATION,
  ContractError,
  DOWNLOAD_TOO_LARGE,
  FixtureTransport,
  HttpTransport,
  NOT_IMPLEMENTED,
  NO_USER_CONTEXT,
  SCOPE_NOT_GRANTED,
  TECHNICAL_TYPES,
  category,
};
