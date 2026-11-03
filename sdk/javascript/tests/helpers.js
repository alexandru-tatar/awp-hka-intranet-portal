"use strict";

/** Hilfen für die SDK-Tests: Testschlüssel, Assertion-Fabrik und eine kleine App mit dem SDK. */

const crypto = require("node:crypto");
const express = require("express");
const { Portal, Config, JwksCache } = (() => {
  const sdk = require("../platform_sdk");
  return { Portal: sdk.Portal, Config: require("../platform_sdk/config").Config, JwksCache: require("../platform_sdk/jwks").JwksCache };
})();

const ISSUER = "https://portal.test/";
const { privateKey, publicKey } = crypto.generateKeyPairSync("rsa", { modulusLength: 2048 });
const KEYS = JwksCache.fixed({ "test-key": publicKey });
const MANIFEST = {
  slug: "noten",
  name: "Noten-Übersicht",
  category: "Studium",
  menu: { label: "Meine Noten", icon: "grades" },
  roles: ["student"],
  adapters: ["noten:read"],
  version: "1.0.0",
};

const b64 = (value) => Buffer.from(typeof value === "string" ? value : JSON.stringify(value)).toString("base64url");

/** Unterschreibt Claims mit dem Testschlüssel. `key: null` erzeugt einen Token ohne Signatur (alg none). */
function sign(claims, { header = { alg: "RS256", kid: "test-key" }, key = privateKey } = {}) {
  const signingInput = `${b64(header)}.${b64(claims)}`;
  if (key === null) return `${signingInput}.`;
  const signature = crypto.sign("RSA-SHA256", Buffer.from(signingInput), key).toString("base64url");
  return `${signingInput}.${signature}`;
}

function makeToken(overrides = {}) {
  const now = Math.floor(Date.now() / 1000);
  return sign({
    iss: ISSUER,
    aud: ["noten", "portal", "adapters"],
    sub: "student-test",
    name: "Erika Musterfrau",
    roles: ["student"],
    v: 1,
    iat: now,
    exp: now + 60,
    ...overrides,
  });
}

function makePortal({ dev = false } = {}) {
  const config = new Config({
    env: "test",
    slug: "noten",
    basePath: "",
    apiUrl: "http://127.0.0.1:9", // nicht erreichbar: layout() nimmt das Ersatz-Menü
    adaptersUrl: null,
    issuer: ISSUER,
    dev,
    manifest: MANIFEST,
  });
  const portal = new Portal(config);
  portal.jwks = KEYS;
  return portal;
}

function makeApp(portal) {
  const app = express();
  portal.install(app);
  const router = portal.router();

  router.get("/", async (req, res) => {
    const html = await portal.layout({ title: "Start", body: "<h1>Start</h1>", current: portal.url("/"), user: req.portal.user });
    res.type("html").send(html);
  });
  router.get("/nur-professor", portal.requires("professor"), (_req, res) => {
    res.json({ ok: true });
  });
  router.get("/noten", async (req, res) => {
    const result = await portal.adapters.noten.listMyGrades(req);
    res.json({ count: result.items.length });
  });

  app.use(portal.url("/"), router);
  return app;
}

/** Startet die App auf einem freien Port; liefert `base` und `close()`. */
async function serve(app) {
  const server = await new Promise((resolve) => {
    const s = app.listen(0, "127.0.0.1", () => resolve(s));
  });
  return {
    base: `http://127.0.0.1:${server.address().port}`,
    close: () => new Promise((resolve) => server.close(resolve)),
  };
}

module.exports = { ISSUER, KEYS, MANIFEST, privateKey, sign, makeToken, makePortal, makeApp, serve };
