"use strict";

/**
 * Clients für die Schnittstellen (06 §8).
 *
 * Vorläufig von Hand geschrieben. Später erzeugt `tools/gen_clients.py` diesen Ordner
 * aus den OpenAPI-Dateien der Plattform. Ein Ordner je System: bwsync/, noten/.
 */

const { BwSyncClient } = require("./bwsync");
const { NotenClient } = require("./noten");
const { FixtureTransport, HttpTransport } = require("./transport");

class Adapters {
  constructor(config) {
    const transport = config.adaptersUrl ? new HttpTransport(config.adaptersUrl) : new FixtureTransport();
    this.noten = new NotenClient(transport);
    this.bwsync = new BwSyncClient(transport);
  }
}

module.exports = { Adapters };
