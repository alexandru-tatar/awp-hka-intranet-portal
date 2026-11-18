"use strict";

/** connect.js im Browser nachgestellt (node:vm): Zustände und Fehlertypen, ohne Oberfläche. */

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const { test } = require("node:test");
const { SCRIPT_FILE, POPUP_BLOCKED, ABORTED, SESSION_EXPIRED } = require("../platform_sdk/adapters/bwsync/connect");

const SOURCE = fs.readFileSync(SCRIPT_FILE, "utf-8");

/** Lädt das Skript mit Attrappen für window.open, fetch und setTimeout (sofort). */
function load({ answers, popup = true }) {
  const calls = [];
  const tab = { opener: "seite", location: { href: "" }, closed: false, close() { this.closed = true; } };
  const window = { open: () => (popup ? tab : null) };
  const fetch = async (url, init) => {
    calls.push([init.method, url, init.credentials]);
    const [status, body] = answers.shift();
    return { ok: status >= 200 && status < 300, status, json: async () => body };
  };
  vm.runInNewContext(SOURCE, { window, fetch, setTimeout: (fn) => fn(), Promise, Date, Number, Object });
  return { api: window.PortalBwSync, calls, tab };
}

function run(api) {
  const states = [];
  return new Promise((resolve) => {
    api.connect((s) => {
      states.push(s);
      if (s.state !== "waiting") resolve(states);
    });
  });
}

test("verbinden: wartet, öffnet Anmeldeseite, meldet verbunden", async () => {
  const { api, calls, tab } = load({ answers: [
    [200, { login_url: "https://dav.example.test/login", expires_in: 60 }],
    [200, { state: "pending" }],
    [200, { state: "linked", account: "erika" }],
  ] });
  const states = await run(api);
  assert.deepEqual(states.map((s) => s.state), ["waiting", "linked"]);
  assert.equal(states[1].account, "erika");
  assert.equal(tab.opener, null);
  assert.equal(tab.location.href, "https://dav.example.test/login");
  assert.deepEqual(calls.map((c) => c.slice(0, 2)), [
    ["POST", "/connect/bwsync/start"], ["POST", "/connect/bwsync/poll"], ["POST", "/connect/bwsync/poll"],
  ]);
  assert.ok(calls.every((c) => c[2] === "same-origin"));
});

test("verbinden: Fehlertypen", async () => {
  let { api } = load({ answers: [], popup: false });
  assert.deepEqual({ ...(await run(api)).at(-1) }, { state: "error", type: POPUP_BLOCKED, status: 0 });
  ({ api } = load({ answers: [[401, {}]] }));
  assert.equal((await run(api)).at(-1).type, SESSION_EXPIRED);
  const loaded = load({ answers: [[403, { type: "urn:hka:problem:bwsync-forbidden", detail: "x" }]] });
  assert.deepEqual({ ...(await run(loaded.api)).at(-1) }, { state: "error", type: "bwsync-forbidden", status: 403 });
  assert.ok(loaded.tab.closed);
  ({ api } = load({ answers: [[200, { login_url: "http://unsicher.test/" }]] }));
  assert.equal((await run(api)).at(-1).type, "backend-unavailable");
  ({ api } = load({ answers: [[200, { login_url: "https://dav.test/" }], [200, { state: "none" }]] }));
  assert.equal((await run(api)).at(-1).type, ABORTED);
});

test("trennen und Zustand", async () => {
  let { api, calls } = load({ answers: [[200, { linked: false, revoked: null }]] });
  assert.deepEqual({ ...(await api.disconnect()) }, { linked: false, revoked: null });
  assert.deepEqual(calls[0].slice(0, 2), ["DELETE", "/connect/bwsync"]);
  ({ api } = load({ answers: [[503, { type: "urn:hka:problem:backend-unavailable" }]] }));
  await assert.rejects(api.disconnect(), (err) => err.type === "backend-unavailable" && err.status === 503);
  ({ api } = load({ answers: [[200, { linked: true, account: "erika" }]] }));
  assert.deepEqual({ ...(await api.status()) }, { linked: true, account: "erika" });
});
