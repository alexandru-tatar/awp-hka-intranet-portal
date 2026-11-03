"use strict";

/**
 * Portal-SDK für JavaScript (vorläufig, nach Architekturvorschlag 06-portal-sdk.md).
 *
 * Verwaltete Dateien: nicht verändern (sonst PF-103). Ersatz durch `make sdk-update`,
 * sobald die Plattform das SDK liefert.
 */

const { User } = require("./context");
const { AdapterError } = require("./errors");
const { Portal } = require("./portal");

module.exports = { AdapterError, Portal, User };
