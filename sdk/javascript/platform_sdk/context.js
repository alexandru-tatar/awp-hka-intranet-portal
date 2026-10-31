"use strict";

/** Angemeldete Person und Kontext der laufenden Anfrage (06 §3.1, §8). */

const crypto = require("node:crypto");
const { AsyncLocalStorage } = require("node:async_hooks");

class User {
  constructor({ sub, name, roles, email = null }) {
    this.sub = sub;
    this.name = name;
    this.roles = Object.freeze([...roles]);
    this.email = email;
    Object.freeze(this);
  }

  /** Erste 12 Hex-Zeichen von SHA-256(sub), nur zur Zuordnung im Log (06 §11). */
  get hash() {
    return crypto.createHash("sha256").update(this.sub).digest("hex").slice(0, 12);
  }
}

/** Kontext der laufenden Anfrage: { requestId, assertion, user }. */
const requestContext = new AsyncLocalStorage();

function currentAssertion() {
  return requestContext.getStore()?.assertion ?? null;
}

module.exports = { User, requestContext, currentAssertion };
