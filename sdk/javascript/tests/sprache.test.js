"use strict";

/** Deutsch und Englisch im SDK (HKA-101): Sprache aus Accept-Language, Rahmen, Fehlerseiten, Test-Anmeldung. */

const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { after, before, test } = require("node:test");
const { LANGUAGES, TEXTS, pickLanguage } = require("../platform_sdk/i18n");
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

const EN = { "Accept-Language": "en-GB,en;q=0.9" };
const student = (extra = {}) => ({ "X-Portal-Assertion": makeToken(), ...extra });

test("pickLanguage", () => {
  const cases = [
    [undefined, "de"], ["", "de"], ["en", "en"], ["en-GB,en;q=0.9,de;q=0.8", "en"], ["de-DE,de;q=0.9,en;q=0.8", "de"],
    ["fr,en;q=0.5", "en"], ["fr-CH,fr;q=0.9", "de"], ["*", "de"], ["en;q=0", "de"], ["en;q=abc", "de"],
    ["en;q=inf", "de"], ["EN-us", "en"], ["de;q=0.5,en;q=0.9", "en"], ["en,".repeat(200), "de"],
  ];
  for (const [header, expected] of cases) assert.equal(pickLanguage(header), expected, String(header));
});

test("Texte: beide Sprachen, gleiche Schlüssel, in Python und JavaScript dieselbe Datei", () => {
  assert.deepEqual(Object.keys(TEXTS).sort(), [...LANGUAGES].sort());
  assert.deepEqual(Object.keys(TEXTS.de).sort(), Object.keys(TEXTS.en).sort());
  assert.ok(Object.values(TEXTS.en).every((text) => text.length > 0));
  const js = path.join(__dirname, "..", "platform_sdk", "texts.json");
  const py = path.join(__dirname, "..", "..", "python", "platform_sdk", "texts.json");
  assert.ok(fs.readFileSync(js).equals(fs.readFileSync(py)));
});

test("Seitenrahmen auf Englisch", async () => {
  const html = await (await fetch(`${prod.base}/`, { headers: student(EN) })).text();
  assert.match(html, /<html lang="en">/);
  assert.ok(html.includes("Skip to content") && html.includes("Signed in as"));
  assert.ok(html.includes('aria-label="Main navigation"') && html.includes("<summary>Menu</summary>"));
  assert.ok(html.includes("Do you want to log out of the portal?") && html.includes(">Cancel</button>"));
  assert.ok(!html.includes("Zum Inhalt") && !html.includes("Abmelden"));
});

test("Seitenrahmen: Standard und unbekannte Sprache sind Deutsch", async () => {
  const de = await (await fetch(`${prod.base}/`, { headers: student() })).text();
  assert.match(de, /<html lang="de">/);
  assert.ok(de.includes("Abmelden") && !de.includes("Skip to content"));
  const fr = await (await fetch(`${prod.base}/`, { headers: student({ "Accept-Language": "fr" }) })).text();
  assert.match(fr, /<html lang="de">/);
});

test("ohne Assertion: 401 auf Englisch, HTML und problem+json", async () => {
  const html = await fetch(`${prod.base}/`, { headers: { Accept: "text/html", ...EN } });
  assert.equal(html.status, 401);
  const text = await html.text();
  assert.match(text, /<html lang="en">/);
  assert.ok(text.includes("Login missing") && text.includes("log in there"));
  const json = await fetch(`${prod.base}/`, { headers: EN });
  assert.equal(json.headers.get("content-type"), "application/problem+json");
  assert.equal((await json.json()).title, "Login missing");
});

test("kein Zugriff auf Englisch", async () => {
  const response = await fetch(`${prod.base}/nur-professor`, { headers: student({ Accept: "text/html", ...EN }) });
  assert.equal(response.status, 403);
  const text = await response.text();
  assert.ok(text.includes("No access") && text.includes("This page is not available for your role."));
  assert.ok(!text.includes("Kein Zugriff"));
});

test("Menü-Anfrage an das Portal trägt die Sprache", async () => {
  const seen = [];
  const fakePortal = http.createServer((req, res) => {
    seen.push(req.headers["accept-language"]);
    res.writeHead(200, { "Content-Type": "text/html", "X-Portal-Kit": "kit-abc" });
    res.end("<nav>Menü vom Portal</nav>");
  });
  await new Promise((resolve) => fakePortal.listen(0, "127.0.0.1", resolve));
  const app = await serve(makeApp(makePortal({ apiUrl: `http://127.0.0.1:${fakePortal.address().port}` })));
  try {
    await fetch(`${app.base}/`, { headers: student(EN) });
    await fetch(`${app.base}/`, { headers: student() });
    assert.deepEqual(seen, ["en", "de"]);
  } finally {
    await app.close();
    await new Promise((resolve) => fakePortal.close(resolve));
  }
});

test("Test-Anmeldung auf Englisch", async () => {
  const en = await (await fetch(`${dev.base}/__dev/login`, { headers: EN })).text();
  assert.match(en, /<html lang="en">/);
  assert.ok(en.includes("Test login") && en.includes("Roles from the manifest") && !en.includes("Testperson"));
  const de = await (await fetch(`${dev.base}/__dev/login`)).text();
  assert.ok(/<html lang="de">/.test(de) && de.includes("Test-Anmeldung"));
});

test("portal.language(req) für eigene Texte der App (R-UI-7)", () => {
  const portal = makePortal();
  const req = (header) => ({ headers: header === undefined ? {} : { "accept-language": header } });
  assert.equal(portal.language(req()), "de");
  assert.equal(portal.language(req("en-GB,en;q=0.9")), "en");
  assert.equal(portal.language(req("fr")), "de");
  assert.equal(portal.language(req("de,en;q=0.5")), "de");
});
