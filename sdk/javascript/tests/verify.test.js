"use strict";

/** Prüfung der Assertion (06 §5). Auszug aus dem gemeinsamen Katalog F1–F22 (06 §9). */

const assert = require("node:assert/strict");
const { test } = require("node:test");
const { VerifyError } = require("../platform_sdk/errors");
const { verify } = require("../platform_sdk/verify");
const { ISSUER, KEYS, makeToken, sign } = require("./helpers");

const check = (token) => verify(token, { keys: KEYS, issuer: ISSUER, audience: "noten" });
const now = () => Math.floor(Date.now() / 1000);

async function expectError(token, code) {
  await assert.rejects(check(token), (err) => err instanceof VerifyError && err.code === code);
}

test("F1 gültig", async () => assert.equal((await check(makeToken())).sub, "student-test"));
test("F2 mit E-Mail", async () => {
  assert.equal((await check(makeToken({ email: "erika@test.hka.example" }))).email, "erika@test.hka.example");
});
test("F3 aud als Text", async () => assert.ok(await check(makeToken({ aud: "noten" }))));
test("F4 innerhalb der Toleranz", async () => assert.ok(await check(makeToken({ exp: now() - 3 }))));
test("F5 abgelaufen", () => expectError(makeToken({ exp: now() - 40 }), "Expired"));
test("F6 noch nicht gültig", () => expectError(makeToken({ iat: now() + 30 }), "NotYetValid"));
test("F7 falsche Zielgruppe", () => expectError(makeToken({ aud: ["other", "portal"] }), "WrongAudience"));
test("F8 falscher Aussteller", () => expectError(makeToken({ iss: "https://boese.example/" }), "WrongIssuer"));
test("F9 alg none", () => expectError(sign({ sub: "x" }, { header: { alg: "none", kid: "test-key" }, key: null }), "BadAlgorithm"));
test("F12 veränderte Daten", async () => {
  const [header, , signature] = makeToken().split(".");
  const otherPayload = makeToken({ roles: ["platform-admin"] }).split(".")[1];
  await expectError(`${header}.${otherPayload}.${signature}`, "BadSignature");
});
test("F14 unbekannter Schlüssel", () => expectError(sign({ sub: "x" }, { header: { alg: "RS256", kid: "fremd" } }), "UnknownKey"));
test("F15 ohne kid", () => expectError(sign({ sub: "x" }, { header: { alg: "RS256" } }), "MissingKid"));
test("F17 Version 2", () => expectError(makeToken({ v: 2 }), "UnsupportedVersion"));
test("F18 Rollen kein Array", () => expectError(makeToken({ roles: "student" }), "BadRoles"));
test("F19 leeres sub", () => expectError(makeToken({ sub: "" }), "MissingSubject"));
test("F20 unbekannter Claim", async () => assert.ok(await check(makeToken({ foo: "bar" }))));

for (const token of ["", "a.b", "x.y.z", "a".repeat(9000)]) {
  test(`F21/F22 kaputt: ${token.slice(0, 8) || "leer"}`, () => expectError(token, "Malformed"));
}
