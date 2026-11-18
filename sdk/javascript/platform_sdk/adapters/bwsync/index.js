"use strict";

/** bwSync&Share (Dateien und Ordner im eigenen Konto). Beschreibung: README.md in diesem Ordner. */

const connect = require("./connect");
const errors = require("./errors");
const paths = require("./paths");
const { BwSyncClient } = require("./client");

module.exports = { BwSyncClient, connect, errors, paths };
