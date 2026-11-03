"use strict";

/** Nunjucks-Umgebung des SDK mit eingeschaltetem autoescape. */

const path = require("node:path");
const nunjucks = require("nunjucks");

const env = new nunjucks.Environment(new nunjucks.FileSystemLoader(path.join(__dirname, "templates")), {
  autoescape: true,
});

module.exports = { env };
