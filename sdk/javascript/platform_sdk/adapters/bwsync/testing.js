"use strict";

/**
 * bwSync&Share für Tests der App: ein Konto im Speicher, das sich wie der Adapter verhält (gleiche Fehlertypen).
 *
 *   const { FakeBwSync } = require("../platform_sdk/adapters/bwsync/testing");
 *   const bwsync = new FakeBwSync().install(portal); // portal.adapters.bwsync arbeitet jetzt mit dem Fake
 *   // nach dem Test: bwsync.uninstall()
 */

const zlib = require("node:zlib");
const { Readable } = require("node:stream");
const { AdapterError } = require("../../errors");
const { BACKEND_UNAVAILABLE, DOWNLOAD_TOO_LARGE, NO_USER_CONTEXT } = require("../transport");
const errors = require("./errors");
const { BwSyncClient } = require("./client");

const MODIFIED = "2026-11-16T13:28:22+00:00";
const FILES = "/bwsync/files/";
const FOLDERS = "/bwsync/folders/";
const ZIP = "/bwsync/zip/";

/** Wie `AdapterStream`: Inhalt in Stücken, `close()` darf mehrfach kommen. */
class FakeStream {
  constructor(data, chunk = 64 * 1024) {
    this._parts = [];
    for (let i = 0; i < data.length; i += chunk) this._parts.push(data.subarray(i, i + chunk));
    if (!this._parts.length) this._parts.push(Buffer.alloc(0));
    this.closed = false;
  }

  async *[Symbol.asyncIterator]() {
    try {
      for (const part of this._parts) yield part;
    } finally {
      await this.close();
    }
  }

  readable() {
    const readable = Readable.from(this);
    readable.on("close", () => this.close());
    return readable;
  }

  async close() {
    this.closed = true;
  }
}

// --- kleines ZIP (ohne Abhängigkeit), Einträge mit Deflate ------------------------------------------------------

const CRC_TABLE = Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});

function crc32(buf) {
  let c = 0xffffffff;
  for (const b of buf) c = CRC_TABLE[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function zip(files) {
  const local = [];
  const central = [];
  let offset = 0;
  for (const [name, data] of files) {
    const nameBuf = Buffer.from(name, "utf-8");
    const packed = zlib.deflateRawSync(data);
    const crc = crc32(data);
    const head = Buffer.alloc(30);
    head.writeUInt32LE(0x04034b50, 0);
    head.writeUInt16LE(20, 4);
    head.writeUInt16LE(0x0800, 6); // UTF-8-Namen
    head.writeUInt16LE(8, 8);
    head.writeUInt32LE(crc, 14);
    head.writeUInt32LE(packed.length, 18);
    head.writeUInt32LE(data.length, 22);
    head.writeUInt16LE(nameBuf.length, 26);
    const dir = Buffer.alloc(46);
    dir.writeUInt32LE(0x02014b50, 0);
    dir.writeUInt16LE(20, 4);
    dir.writeUInt16LE(20, 6);
    dir.writeUInt16LE(0x0800, 8);
    dir.writeUInt16LE(8, 10);
    dir.writeUInt32LE(crc, 16);
    dir.writeUInt32LE(packed.length, 20);
    dir.writeUInt32LE(data.length, 24);
    dir.writeUInt16LE(nameBuf.length, 28);
    dir.writeUInt32LE(offset, 42);
    local.push(head, nameBuf, packed);
    central.push(dir, nameBuf);
    offset += head.length + nameBuf.length + packed.length;
  }
  const centralBuf = Buffer.concat(central);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(files.length, 8);
  end.writeUInt16LE(files.length, 10);
  end.writeUInt32LE(centralBuf.length, 12);
  end.writeUInt32LE(offset, 16);
  return Buffer.concat([...local, centralBuf, end]);
}

function parent(pathName) {
  const i = pathName.lastIndexOf("/");
  return i < 0 ? "" : pathName.slice(0, i);
}

function fail(status, kind) {
  return new AdapterError(status, kind, "Fake");
}

/**
 * Konto im Speicher. `folders` (Set von Pfaden, `""` = Wurzel) und `files` (Map Pfad → Buffer) darf der Test setzen.
 * - `calls`: jeder Aufruf als `[methode, pfad, body]` (Pfad ohne URL-Kodierung).
 * - `fail = [status, type]`: jeder folgende Aufruf scheitert so (`type` null → `backend-unavailable`).
 * - `linked`: Antwort von `isLinked()`; `false` lässt alle Dateiaufrufe mit `bwsync-not-linked` scheitern.
 * - `listing`: feste Antwort (Objekt) für `list()`, z. B. um `truncated`/`skipped` zu testen.
 */
class FakeBwSync {
  constructor() {
    this.folders = new Set([""]);
    this.files = new Map();
    this.calls = [];
    this.fail = null;
    this.linked = true;
    this.listing = null;
    this.streams = [];
    this._installed = null;
  }

  // --- Einbau ---------------------------------------------------------------------------------------------------

  client() {
    return new BwSyncClient(this);
  }

  /** `portal.adapters.bwsync` durch einen Client mit diesem Fake ersetzen (`uninstall` stellt zurück). */
  install(portal) {
    this._installed = [portal, portal.adapters.bwsync];
    portal.adapters.bwsync = this.client();
    return this;
  }

  uninstall() {
    if (!this._installed) return;
    const [portal, original] = this._installed;
    portal.adapters.bwsync = original;
    this._installed = null;
  }

  // --- Hilfen ---------------------------------------------------------------------------------------------------

  /** Datei samt fehlender Elternordner anlegen. */
  addFile(pathName, data = Buffer.alloc(0)) {
    const parts = pathName.split("/");
    for (let i = 1; i < parts.length; i += 1) this.folders.add(parts.slice(0, i).join("/"));
    this.files.set(pathName, Buffer.from(data));
  }

  exists(pathName) {
    return this.folders.has(pathName) || this.files.has(pathName);
  }

  _children(pathName) {
    return [...this.folders, ...this.files.keys()].filter((p) => p && parent(p) === pathName);
  }

  _call(req, method, pathName, body = null) {
    if (!req?.portal?.assertion) {
      // wie der echte Transport: nur während einer Anfrage
      throw new AdapterError(500, NO_USER_CONTEXT, "Aufruf außerhalb einer Anfrage einer angemeldeten Person.");
    }
    const decoded = decodeURIComponent(pathName);
    this.calls.push([method, decoded, body]);
    if (this.fail) throw fail(this.fail[0], this.fail[1] || BACKEND_UNAVAILABLE);
    if (!this.linked && decoded !== "/bwsync/link") throw fail(403, errors.NOT_LINKED);
    return decoded;
  }

  // --- Transport (wie HttpTransport) ------------------------------------------------------------------------------

  async get(req, pathName) {
    const p = this._call(req, "GET", pathName);
    if (p === "/bwsync/link") return { linked: this.linked };
    if (!p.startsWith(FOLDERS)) throw new Error(`unerwarteter Aufruf GET ${p}`);
    const rel = p.slice(FOLDERS.length);
    if (this.listing !== null) return this.listing;
    if (this.files.has(rel)) throw fail(409, errors.NOT_A_FOLDER);
    if (!this.folders.has(rel)) throw fail(404, errors.NOT_FOUND);
    const names = this._children(rel).sort((a, b) => {
      const fa = this.folders.has(a) ? 0 : 1;
      const fb = this.folders.has(b) ? 0 : 1;
      if (fa !== fb) return fa - fb;
      const la = a.toLowerCase();
      const lb = b.toLowerCase();
      return la < lb ? -1 : la > lb ? 1 : 0;
    });
    const entries = names.map((p2) => ({
      name: p2.slice(p2.lastIndexOf("/") + 1),
      type: this.folders.has(p2) ? "folder" : "file",
      size: this.folders.has(p2) ? null : this.files.get(p2).length,
      modified: MODIFIED,
    }));
    return { path: rel, entries, truncated: false, skipped: 0 };
  }

  async send(req, method, pathName, body = null) {
    const p = this._call(req, method, pathName, body);
    if (p === "/bwsync/move" && method === "POST") return this._move(body.from, body.to);
    if (p.startsWith(FOLDERS)) {
      const rel = p.slice(FOLDERS.length);
      if (method === "POST") {
        if (this.exists(rel)) throw fail(409, errors.EXISTS);
        if (!this.folders.has(parent(rel))) throw fail(409, errors.PARENT_MISSING);
        this.folders.add(rel);
        return undefined;
      }
      if (method === "DELETE") {
        if (this.files.has(rel)) throw fail(409, errors.NOT_A_FOLDER);
        if (rel === "" || !this.folders.has(rel)) throw fail(404, errors.NOT_FOUND);
        // wie der Adapter: mit allem Inhalt (bwSync&Share legt es in den Papierkorb)
        for (const f of [...this.folders]) if (f === rel || f.startsWith(`${rel}/`)) this.folders.delete(f);
        for (const k of [...this.files.keys()]) if (k.startsWith(`${rel}/`)) this.files.delete(k);
        return undefined;
      }
    }
    if (p.startsWith(FILES) && method === "DELETE") {
      const rel = p.slice(FILES.length);
      if (this.folders.has(rel)) throw fail(409, errors.NOT_A_FILE);
      if (!this.files.has(rel)) throw fail(404, errors.NOT_FOUND);
      this.files.delete(rel);
      return undefined;
    }
    throw new Error(`unerwarteter Aufruf ${method} ${p}`);
  }

  _move(source, target) {
    if (source === target || target.startsWith(`${source}/`)) throw fail(400, errors.MOVE_INTO_SELF);
    if (!this.exists(source)) throw fail(404, errors.NOT_FOUND);
    if (this.exists(target)) throw fail(409, errors.EXISTS);
    if (!this.folders.has(parent(target))) throw fail(409, errors.PARENT_MISSING);
    if (this.files.has(source)) {
      this.files.set(target, this.files.get(source));
      this.files.delete(source);
      return;
    }
    for (const p of [...this.folders].sort()) {
      if (p === source || p.startsWith(`${source}/`)) {
        this.folders.delete(p);
        this.folders.add(target + p.slice(source.length));
      }
    }
    for (const p of [...this.files.keys()]) {
      if (p.startsWith(`${source}/`)) {
        this.files.set(target + p.slice(source.length), this.files.get(p));
        this.files.delete(p);
      }
    }
  }

  async putBytes(req, pathName, data) {
    const rel = this._call(req, "PUT", pathName, data.length).slice(FILES.length);
    if (data.length > 10 * 1024 * 1024) throw fail(413, errors.TOO_LARGE);
    if (this.exists(rel)) throw fail(412, errors.EXISTS);
    if (!this.folders.has(parent(rel))) throw fail(409, errors.PARENT_MISSING);
    this.files.set(rel, Buffer.from(data));
  }

  async getBytes(req, pathName, { maxBytes }) {
    const rel = this._call(req, "GET", pathName).slice(FILES.length);
    if (!this.files.has(rel)) throw fail(404, errors.NOT_FOUND);
    if (this.files.get(rel).length > maxBytes) {
      throw new AdapterError(413, DOWNLOAD_TOO_LARGE, `mehr als maxBytes=${maxBytes}`);
    }
    return this.files.get(rel);
  }

  async openStream(req, pathName) {
    const rel = this._call(req, "GET", pathName).slice(ZIP.length);
    if (rel === "" || !this.folders.has(rel)) throw fail(404, errors.NOT_FOUND);
    const inside = [...this.files.entries()].filter(([name]) => name.startsWith(`${rel}/`)).sort(([a], [b]) => (a < b ? -1 : 1));
    const stream = new FakeStream(zip(inside));
    this.streams.push(stream);
    return stream;
  }
}

module.exports = { FakeBwSync, FakeStream, MODIFIED };
