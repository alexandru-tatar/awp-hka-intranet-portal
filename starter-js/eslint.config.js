"use strict";

const js = require("@eslint/js");
const globals = require("globals");

module.exports = [
  { ignores: ["node_modules/", "coverage/"] },
  js.configs.recommended,
  {
    files: ["**/*.js"],
    languageOptions: { sourceType: "commonjs", globals: { ...globals.node } },
  },
  {
    files: ["tests/**/*.js"],
    languageOptions: { globals: { ...globals.jest } },
  },
];
