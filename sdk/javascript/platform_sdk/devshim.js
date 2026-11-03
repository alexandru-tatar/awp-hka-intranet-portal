"use strict";

/** Test-Anmeldung für den Entwicklungsmodus (06 §7). Im Betrieb nie aktiv. */

const crypto = require("node:crypto");
const express = require("express");
const { User } = require("./context");
const { env } = require("./templates");

const COOKIE = "portal_dev";
const KEY = crypto.randomBytes(32); // neu bei jedem Start: alte Test-Anmeldungen verfallen

const TEST_PERSONS = [
  { sub: "student-test", name: "Erika Musterfrau", hint: "mit Noten" },
  { sub: "student-empty", name: "Max Mustermann", hint: "ohne Noten" },
];

function sign(data) {
  return crypto.createHmac("sha256", KEY).update(data).digest("hex");
}

function readCookie(req, name) {
  for (const part of (req.headers.cookie ?? "").split(";")) {
    const [key, ...rest] = part.trim().split("=");
    if (key === name) return rest.join("=");
  }
  return "";
}

function userFromCookie(req) {
  const raw = readCookie(req, COOKIE);
  const [payload, signature = ""] = raw.split(".");
  if (!payload) return null;
  const expected = Buffer.from(sign(payload));
  const given = Buffer.from(signature);
  if (expected.length !== given.length || !crypto.timingSafeEqual(expected, given)) return null;
  const data = JSON.parse(Buffer.from(payload, "base64url").toString("utf-8"));
  return new User({ sub: data.sub, name: data.name, roles: data.roles, email: data.email ?? null });
}

const asList = (value) => (value === undefined ? [] : Array.isArray(value) ? value : [value]);

function router(portal) {
  const r = express.Router();
  const manifestRoles = portal.manifest.roles;

  r.get("/login", (_req, res) => {
    res.type("html").send(env.render("dev_login.html", { persons: TEST_PERSONS, roles: manifestRoles, app: portal.manifest.name }));
  });

  r.post("/login", express.urlencoded({ extended: false }), (req, res) => {
    const form = req.body ?? {};
    const person = TEST_PERSONS.find((p) => p.sub === form.sub) ?? TEST_PERSONS[0];
    const roles = asList(form.roles).map(String);
    for (const extra of String(form.extra_roles ?? "").replaceAll(",", " ").split(/\s+/)) {
      if (extra && !roles.includes(extra)) roles.push(extra);
    }
    const payload = Buffer.from(JSON.stringify({ sub: person.sub, name: person.name, roles })).toString("base64url");
    res.append("Set-Cookie", `${COOKIE}=${payload}.${sign(payload)}; HttpOnly; SameSite=Lax; Path=/`);
    res.redirect(303, portal.config.basePath || "/");
  });

  return r;
}

module.exports = { router, userFromCookie, TEST_PERSONS, COOKIE };
