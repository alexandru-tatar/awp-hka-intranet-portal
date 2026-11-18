"use strict";

/**
 * Noten für Tests der App: feste Noten je Person im Speicher, ohne Adapter.
 *
 *   const { FakeNoten } = require("../platform_sdk/adapters/noten/testing");
 *   const fake = new FakeNoten({ "test-person": [{ module: "Mathe 1", semester: "WS 2025/26", grade: "1,3", credits: 5 }] });
 *   fake.install(portal);
 */

const { AdapterError } = require("../../errors");
const { BACKEND_UNAVAILABLE, NO_USER_CONTEXT } = require("../transport");
const { NotenClient } = require("./client");

/** `grades`: sub → Liste von Noten (wie `Grade`). `fail = [status, type]` wie bei FakeBwSync. */
class FakeNoten {
  constructor(grades = {}) {
    this.grades = grades;
    this.calls = [];
    this.fail = null;
    this._installed = null;
  }

  client() {
    return new NotenClient(this);
  }

  install(portal) {
    this._installed = [portal, portal.adapters.noten];
    portal.adapters.noten = this.client();
    return this;
  }

  uninstall() {
    if (!this._installed) return;
    const [portal, original] = this._installed;
    portal.adapters.noten = original;
    this._installed = null;
  }

  async get(req, pathName, params) {
    const user = req?.portal?.user;
    if (!user) throw new AdapterError(500, NO_USER_CONTEXT, "Aufruf außerhalb einer Anfrage einer angemeldeten Person.");
    this.calls.push(["GET", pathName, params]);
    if (this.fail) throw new AdapterError(this.fail[0], this.fail[1] || BACKEND_UNAVAILABLE, "Fake");
    if (pathName !== "/v1/noten/me/grades") throw new Error(`unerwarteter Aufruf GET ${pathName}`);
    let items = this.grades[user.sub] ?? [];
    if (params?.semester) items = items.filter((g) => g.semester === params.semester);
    return { items };
  }
}

module.exports = { FakeNoten };
