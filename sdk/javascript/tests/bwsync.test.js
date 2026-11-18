"use strict";

/** bwSync-Client über HTTP gegen einen kleinen Adapter auf localhost (wie test_bwsync.py). */

const assert = require("node:assert/strict");
const http = require("node:http");
const { after, before, test } = require("node:test");
const { AdapterError } = require("../platform_sdk");
const { BwSyncClient, errors } = require("../platform_sdk/adapters/bwsync");
const transport = require("../platform_sdk/adapters/transport");

let server;
let base;
let handler;
const seen = [];

before(async () => {
  server = http.createServer((request, response) => {
    const chunks = [];
    request.on("data", (c) => chunks.push(c));
    request.on("end", () => {
      const body = Buffer.concat(chunks);
      seen.push({ method: request.method, url: request.url, headers: request.headers, body });
      handler(request, response, body);
    });
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  base = `http://127.0.0.1:${server.address().port}`;
});

after(() => new Promise((resolve) => server.close(resolve)));

const req = { portal: { assertion: "tok", requestId: "rid-1", user: { sub: "p" } } };

function client() {
  seen.length = 0;
  return new BwSyncClient(new transport.HttpTransport(base));
}

function problem(response, status, kind) {
  response.writeHead(status, { "Content-Type": "application/problem+json" });
  response.end(JSON.stringify(kind ? { type: `urn:hka:problem:${kind}`, detail: "Adaptertext" } : { detail: "x" }));
}

async function rejectsWith(promise, status, type) {
  await assert.rejects(promise, (err) => {
    assert.ok(err instanceof AdapterError, String(err));
    assert.deepEqual([err.status, err.type], [status, type]);
    return true;
  });
}

test("Upload, Download, 204 und Kopfzeilen", async () => {
  const files = {};
  handler = (request, response, body) => {
    if (request.method === "PUT") {
      files[request.url] = body;
      response.writeHead(204).end();
    } else {
      response.writeHead(200).end(files[request.url]);
    }
  };
  const bwsync = client();
  await bwsync.upload(req, "Studium/ä b#.txt".replace("#", ""), Buffer.from([0, 1, 2]));
  assert.equal(seen[0].url, "/bwsync/files/Studium/%C3%A4%20b.txt");
  assert.equal(seen[0].headers.authorization, "Bearer tok");
  assert.equal(seen[0].headers["x-request-id"], "rid-1");
  assert.equal(seen[0].headers["content-type"], "application/octet-stream");
  assert.deepEqual([...(await bwsync.download(req, "Studium/ä b.txt"))], [0, 1, 2]);
});

test("ohne Anmeldung kein Aufruf", async () => {
  const bwsync = client();
  await rejectsWith(bwsync.list({}), 500, transport.NO_USER_CONTEXT);
  await rejectsWith(bwsync.upload({}, "a", Buffer.alloc(1)), 500, transport.NO_USER_CONTEXT);
  assert.equal(seen.length, 0);
});

test("Fehlertypen des Adapters kommen bei der App an; ohne type backend-unavailable", async () => {
  for (const [status, kind] of [[403, errors.NOT_LINKED], [409, errors.EXISTS], [404, errors.NOT_FOUND], [423, errors.LOCKED]]) {
    handler = (_q, r) => problem(r, status, kind);
    await rejectsWith(client().mkdir(req, "a"), status, kind);
  }
  handler = (_q, r) => problem(r, 400, null);
  await assert.rejects(client().list(req, "a"), (err) => {
    assert.deepEqual([err.status, err.type, err.detail], [400, transport.BACKEND_UNAVAILABLE, "x"]);
    return true;
  });
  handler = (_q, r) => r.writeHead(302, { Location: "http://evil.test/" }).end();
  await rejectsWith(client().list(req), 302, transport.BACKEND_UNAVAILABLE);
  assert.equal(seen.length, 1); // keine Weiterleitung gefolgt
});

test("Netzfehler ohne Nutzertext", async () => {
  const bwsync = new BwSyncClient(new transport.HttpTransport("http://127.0.0.1:9"));
  await assert.rejects(bwsync.list(req), (err) => {
    assert.deepEqual([err.status, err.type, err.detail], [503, transport.BACKEND_UNAVAILABLE, ""]);
    return true;
  });
});

test("Download-Grenze", async () => {
  handler = (_q, r) => r.writeHead(200).end(Buffer.alloc(100));
  await rejectsWith(client().download(req, "a", { maxBytes: 10 }), 413, transport.DOWNLOAD_TOO_LARGE);
});

test("ungültige Pfade erreichen den Adapter nie", async () => {
  const bwsync = client();
  for (const bad of ["", "../a", "a/../b", "a//b", "a\\b", "a%2f", "a?b", "a#b", "C:x", "a\x00", "x".repeat(256)]) {
    await assert.rejects(bwsync.upload(req, bad, Buffer.alloc(0)), TypeError, bad);
  }
  await assert.rejects(bwsync.downloadZip(req, ""), TypeError);
  await assert.rejects(bwsync.delete(req, "", { folder: true }), TypeError);
  assert.equal(seen.length, 0);
});

test("list: Wurzel, Unterordner, strenge Antwort", async () => {
  handler = (request, r) => {
    r.writeHead(200, { "Content-Type": "application/json" });
    r.end(JSON.stringify({ path: "", entries: [{ name: "a", type: "folder", size: null, modified: null }], truncated: false, skipped: 0 }));
  };
  const bwsync = client();
  assert.equal((await bwsync.list(req)).entries[0].name, "a");
  await bwsync.list(req, "Mein Ordner");
  assert.deepEqual(seen.map((s) => s.url), ["/bwsync/folders/", "/bwsync/folders/Mein%20Ordner"]);
  handler = (_q, r) => r.writeHead(200, { "Content-Type": "application/json" }).end('{"path": "", "entries": []}');
  await rejectsWith(bwsync.list(req), 502, transport.CONTRACT_VIOLATION);
});

test("mkdir, move, delete, isLinked", async () => {
  handler = (request, r) => {
    if (request.url === "/bwsync/link") return r.writeHead(200, { "Content-Type": "application/json" }).end('{"linked": true}');
    return r.writeHead(request.method === "POST" && request.url.startsWith("/bwsync/folders/") ? 201 : 204).end();
  };
  const bwsync = client();
  await bwsync.mkdir(req, "a b");
  await bwsync.move(req, "a b", "c");
  await bwsync.delete(req, "c", { folder: true });
  await bwsync.delete(req, "x.txt");
  assert.equal(await bwsync.isLinked(req), true);
  assert.deepEqual(seen.map((s) => [s.method, s.url]), [
    ["POST", "/bwsync/folders/a%20b"], ["POST", "/bwsync/move"], ["DELETE", "/bwsync/folders/c"],
    ["DELETE", "/bwsync/files/x.txt"], ["GET", "/bwsync/link"],
  ]);
  assert.deepEqual(JSON.parse(seen[1].body), { from: "a b", to: "c" });
  handler = (_q, r) => r.writeHead(200).end("{}");
  await rejectsWith(bwsync.mkdir(req, "a"), 502, transport.CONTRACT_VIOLATION);
});

test("ZIP wird gestreamt und geschlossen; Fehler vor der Antwort", async () => {
  handler = (_q, r) => {
    r.writeHead(200, { "Content-Type": "application/zip" });
    r.write("PK-teil-1");
    r.end("-teil-2");
  };
  const stream = await client().downloadZip(req, "Studium");
  const parts = [];
  for await (const part of stream) parts.push(part);
  assert.equal(Buffer.concat(parts).toString(), "PK-teil-1-teil-2");
  assert.ok(stream.closed);
  await stream.close();
  handler = (_q, r) => problem(r, 404, errors.NOT_FOUND);
  await rejectsWith(client().downloadZip(req, "fehlt"), 404, errors.NOT_FOUND);
});

test("Entwicklungsmodus täuscht bwSync nicht vor", async () => {
  const bwsync = new BwSyncClient(new transport.FixtureTransport());
  for (const call of [bwsync.list(req), bwsync.mkdir(req, "a"), bwsync.upload(req, "a", Buffer.alloc(0)),
    bwsync.download(req, "a"), bwsync.downloadZip(req, "a"), bwsync.isLinked(req)]) {
    await rejectsWith(call, 501, transport.NOT_IMPLEMENTED);
  }
});
