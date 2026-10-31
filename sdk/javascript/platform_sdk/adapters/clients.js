"use strict";

/** Clients je System (06 §8). Jeder Aufruf bekommt die Anfrage (`req`), damit die Person bekannt ist. */

const { AdapterError } = require("../errors");
const { ContractError, gradeList } = require("./models");

const CONTRACT_VIOLATION = "Das System hat unerwartete Daten geliefert. Bitte versuchen Sie es später noch einmal.";

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
      if (err instanceof ContractError) throw new AdapterError(502, "contract-violation", CONTRACT_VIOLATION);
      throw err;
    }
  }
}

module.exports = { NotenClient, CONTRACT_VIOLATION };
