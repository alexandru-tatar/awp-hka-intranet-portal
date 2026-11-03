"use strict";

/**
 * Clients für die Schnittstellen (06 §8).
 *
 * Vorläufig von Hand geschrieben. Später erzeugt `tools/gen_clients.py` diesen Ordner
 * aus den OpenAPI-Dateien der Plattform. Bisher nur Noten; Mail und E-Akte folgen.
 */

const { NotenClient } = require("./clients");
const { FixtureTransport, HttpTransport } = require("./transport");

class Adapters {
  constructor(config) {
    const transport = config.adaptersUrl ? new HttpTransport(config.adaptersUrl) : new FixtureTransport();
    this.noten = new NotenClient(transport);
  }
}

module.exports = { Adapters };
