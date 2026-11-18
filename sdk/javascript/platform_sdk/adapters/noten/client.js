"use strict";

/** Noten: Aufrufe des Noten-Adapters (Beschreibung: README.md in diesem Ordner). */

const { AdapterError } = require("../../errors");
const { CONTRACT_VIOLATION } = require("../transport");
const { ContractError, gradeList } = require("./models");

class NotenClient {
  constructor(transport) {
    this._t = transport;
  }

  async listMyGrades(req, { semester } = {}) {
    const params = semester ? { semester } : null;
    const data = await this._t.get(req, "/v1/noten/me/grades", params);
    try {
      return gradeList(data);
    } catch (err) {
      if (err instanceof ContractError) throw new AdapterError(502, CONTRACT_VIOLATION, "");
      throw err;
    }
  }
}

module.exports = { NotenClient };
