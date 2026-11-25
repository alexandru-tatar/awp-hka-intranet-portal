"use strict";

/** Middleware, Rollen, Seitenrahmen, Entwicklungsmodus, Schnittstellen und Prüfsumme (06 §13: S3, S6, S8, S9, S11). */

const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const os = require("node:os");
const path = require("node:path");
const { after, before, test } = require("node:test");
const { AdapterError } = require("../platform_sdk");
const { FixtureTransport, HttpTransport } = require("../platform_sdk/adapters/transport");
const { Config, DEV_REFUSED } = require("../platform_sdk/config");
const { treeHash, ROOT } = require("../platform_sdk/verify-tree");
const { makeApp, makePortal, makeToken, serve } = require("./helpers");

let prod;
let dev;

before(async () => {
  prod = await serve(makeApp(makePortal()));
  dev = await serve(makeApp(makePortal({ dev: true })));
});
after(async () => {
  await prod.close();
  await dev.close();
});

const student = () => ({ "X-Portal-Assertion": makeToken() });

test("Menü vom Portal: Authorization Bearer statt X-Portal-Assertion (S6)", async () => {
  const seen = [];
  const fakePortal = http.createServer((req, res) => {
    seen.push({ url: req.url, headers: req.headers });
    res.writeHead(200, { "Content-Type": "text/html", "X-Portal-Kit": "kit-abc" });
    res.end('<nav aria-label="Hauptnavigation">Menü vom Portal</nav>');
  });
  await new Promise((resolve) => fakePortal.listen(0, "127.0.0.1", resolve));
  const app = await serve(makeApp(makePortal({ apiUrl: `http://127.0.0.1:${fakePortal.address().port}` })));
  try {
    const token = makeToken();
    const response = await fetch(`${app.base}/`, { headers: { "X-Portal-Assertion": token } });
    const html = await response.text();
    assert.equal(response.status, 200);
    assert.ok(html.includes("Menü vom Portal"));
    assert.ok(html.includes("/_portal/static/kit-abc.css"));
    assert.equal(seen.length, 1);
    assert.equal(seen[0].url, "/nav");
    assert.equal(seen[0].headers.authorization, `Bearer ${token}`);
    assert.equal(seen[0].headers["x-portal-assertion"], undefined);
  } finally {
    await app.close();
    await new Promise((resolve) => fakePortal.close(resolve));
  }
});

test("/healthz ist offen", async () => {
  assert.equal((await fetch(`${prod.base}/healthz`)).status, 200);
});

test("ohne Assertion: 401 als HTML", async () => {
  const response = await fetch(`${prod.base}/`, { headers: { Accept: "text/html" } });
  assert.equal(response.status, 401);
  assert.match(await response.text(), /<html lang="de">/);
});

test("ohne Assertion: 401 als problem+json", async () => {
  const response = await fetch(`${prod.base}/`);
  assert.equal(response.status, 401);
  assert.equal(response.headers.get("content-type"), "application/problem+json");
  assert.equal(response.headers.get("set-cookie"), null);
});

test("jede unbekannte Adresse ohne Anmeldung: 401", async () => {
  assert.equal((await fetch(`${prod.base}/gibt-es-nicht`)).status, 401);
});

test("gültige Assertion: Seitenrahmen mit Ersatz-Menü", async () => {
  const response = await fetch(`${prod.base}/`, { headers: student() });
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /<html lang="de">/);
  assert.ok(html.includes('href="#main"'));
  assert.ok(html.includes('aria-label="Hauptnavigation"')); // Ersatz-Menü, weil das Portal nicht erreichbar ist
  assert.ok(html.includes("Erika Musterfrau"));
  assert.ok(html.includes("/static/app.css"));
  // Abmelden ohne Zwischenseite: Dialog schickt POST /logout an das Gateway; kein Banner im Betrieb
  assert.ok(html.includes('<form id="logout-form" method="post" action="/logout" hidden></form>'));
  assert.ok(html.includes('data-dialog-open="logout-dialog"') && html.includes('data-submit-form="logout-form"'));
  assert.ok(!html.includes("dev-banner") && !html.includes("/__dev/login"));
});

test("install liefert connect.js aus, nur angemeldet", async () => {
  const { SCRIPT_FILE } = require("../platform_sdk/adapters/bwsync/connect");
  const ok = await fetch(`${prod.base}/_sdk/bwsync/connect.js`, { headers: student() });
  assert.equal(ok.status, 200);
  assert.ok(ok.headers.get("content-type").startsWith("text/javascript"));
  assert.equal(ok.headers.get("x-content-type-options"), "nosniff");
  assert.equal(await ok.text(), fs.readFileSync(SCRIPT_FILE, "utf-8"));
  assert.equal((await fetch(`${prod.base}/_sdk/bwsync/connect.js`)).status, 401);
});

test("requires: 403 ohne die Rolle", async () => {
  assert.equal((await fetch(`${prod.base}/nur-professor`, { headers: student() })).status, 403);
});

test("requires: 403 im Browser als Seite im Portal-Rahmen mit Weg zur Startseite (HKA-95)", async () => {
  const response = await fetch(`${prod.base}/nur-professor`, { headers: { ...student(), Accept: "text/html" } });
  const html = await response.text();
  assert.equal(response.status, 403);
  assert.ok(response.headers.get("content-type").startsWith("text/html"));
  assert.ok(html.includes("<title>Kein Zugriff – HKA Portal</title>"));
  assert.ok(html.includes('class="site-header"') && html.includes('aria-label="Hauptnavigation"')); // Rahmen und Menü
  assert.ok(html.includes('href="/_portal/static/kit.css"')); // gestaltet mit dem Kit
  assert.ok(html.includes("<h1>Kein Zugriff</h1>"));
  assert.ok(html.includes("Diese Seite ist für Ihre Rolle nicht freigegeben."));
  assert.ok(html.includes('<a href="/">Zur Startseite des Portals</a>'));
  assert.ok(!html.includes("dev-banner"));
});

test("requires: 403 ohne text/html bleibt problem+json", async () => {
  const response = await fetch(`${prod.base}/nur-professor`, { headers: student() });
  assert.equal(response.status, 403);
  assert.ok(response.headers.get("content-type").startsWith("application/problem+json"));
  const body = await response.json();
  assert.equal(body.type, "urn:hka:problem:403");
  assert.equal(body.title, "Kein Zugriff");
});

test("requires: mit der Rolle erscheint die Fehlerseite nicht (HKA-95)", async () => {
  const headers = { "X-Portal-Assertion": makeToken({ roles: ["professor"] }), Accept: "text/html" };
  const response = await fetch(`${prod.base}/nur-professor`, { headers });
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { ok: true });
});

test("requires: 403 fällt auf die einfache Seite zurück, wenn der Rahmen nicht gebaut werden kann", async () => {
  const portal = makePortal();
  portal._layout.render = async () => {
    throw new Error("kaputt");
  };
  const app = await serve(makeApp(portal));
  try {
    const response = await fetch(`${app.base}/nur-professor`, { headers: { ...student(), Accept: "text/html" } });
    const html = await response.text();
    assert.equal(response.status, 403);
    assert.ok(html.includes("<h1>Kein Zugriff</h1>") && !html.includes("site-header"));
  } finally {
    await app.close();
  }
});

test("Adapter nicht erreichbar", async () => {
  const req = { portal: { assertion: makeToken(), requestId: null } };
  await assert.rejects(new HttpTransport("http://127.0.0.1:9").get(req, "/v1/noten/me/grades", null), (err) => {
    assert.ok(err instanceof AdapterError);
    assert.equal(err.type, "backend-unavailable");
    assert.equal(err.status, 503);
    assert.equal(err.detail, ""); // kein Nutzertext im SDK; den Text wählt die App nach type
    return true;
  });
});

test("Entwicklungsmodus in Produktion abgelehnt", () => {
  const saved = { ...process.env };
  Object.assign(process.env, { PORTAL_DEV: "1", PORTAL_ENV: "production" });
  try {
    assert.throws(() => Config.fromEnv("/dev/null"), { message: DEV_REFUSED });
  } finally {
    process.env = saved;
  }
});

test("Entwicklungsmodus mit Basispfad abgelehnt", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "sdk-"));
  fs.writeFileSync(path.join(dir, "manifest.json"), '{"slug": "noten"}');
  const saved = { ...process.env };
  Object.assign(process.env, { PORTAL_DEV: "1", PORTAL_BASE_PATH: "/apps/noten" });
  try {
    assert.throws(() => Config.fromEnv(path.join(dir, "manifest.json")), { message: DEV_REFUSED });
  } finally {
    process.env = saved;
  }
});

async function devLogin(fields) {
  const response = await fetch(`${dev.base}/__dev/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams(fields),
    redirect: "manual",
  });
  return { Cookie: response.headers.get("set-cookie").split(";")[0] };
}

test("Test-Anmeldung", async () => {
  const first = await fetch(`${dev.base}/`, { redirect: "manual" });
  assert.equal(first.status, 303);
  assert.equal(first.headers.get("location"), "/__dev/login");
  assert.equal((await fetch(`${dev.base}/__dev/login`)).status, 200);
  const cookie = await devLogin([["sub", "student-test"], ["roles", "student"]]);
  const page = await fetch(`${dev.base}/`, { headers: cookie });
  assert.equal(page.status, 200);
  const devHtml = await page.text();
  assert.ok(devHtml.includes("Entwicklungsmodus – Testperson: Erika Musterfrau"));
  assert.ok(devHtml.includes('<a href="/__dev/login">Abmelden</a>') && !devHtml.includes("logout-form"));
  assert.deepEqual(await (await fetch(`${dev.base}/noten`, { headers: cookie })).json(), { count: 5 });
  assert.equal((await fetch(`${dev.base}/nur-professor`, { headers: cookie })).status, 403);
});

test("Test-Anmeldung: Seite „Kein Zugriff“ im Rahmen zeigt den Entwicklungsmodus (HKA-95)", async () => {
  const cookie = await devLogin([["sub", "student-test"], ["roles", "student"]]);
  const response = await fetch(`${dev.base}/nur-professor`, { headers: { ...cookie, Accept: "text/html" } });
  const html = await response.text();
  assert.equal(response.status, 403);
  assert.ok(html.includes("Entwicklungsmodus – Testperson: Erika Musterfrau"));
  assert.ok(html.includes('href="/__dev/kit/kit.css"'));
  assert.ok(html.includes('<a href="/">Zur Startseite des Portals</a>'));
});

test("Test-Anmeldung mit weiterer Rolle", async () => {
  const cookie = await devLogin([["sub", "student-empty"], ["extra_roles", "professor"]]);
  assert.equal((await fetch(`${dev.base}/nur-professor`, { headers: cookie })).status, 200);
  assert.deepEqual(await (await fetch(`${dev.base}/noten`, { headers: cookie })).json(), { count: 0 });
});

test("Test-Anmeldung: gefälschtes Cookie wird abgelehnt", async () => {
  const response = await fetch(`${dev.base}/`, { headers: { Cookie: "portal_dev=e30.abc" }, redirect: "manual" });
  assert.equal(response.status, 303);
});

test("Testdaten ohne Person", async () => {
  await assert.rejects(new FixtureTransport().get({}, "/v1/noten/me/grades", null), (err) => {
    assert.equal(err.type, "no-user-context");
    return true;
  });
});

test("Prüfsumme ändert sich bei jeder Veränderung", () => {
  const tree = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "sdk-")), "platform_sdk");
  fs.cpSync(ROOT, tree, { recursive: true, filter: (src) => !src.includes("node_modules") });
  const before = treeHash(tree);
  fs.writeFileSync(path.join(tree, "VERSION"), "9.9.9\n");
  assert.notEqual(treeHash(tree), before);
  fs.rmSync(path.join(tree, "VERSION"));
  assert.notEqual(treeHash(tree), before);
});
