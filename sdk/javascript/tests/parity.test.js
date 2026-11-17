"use strict";

/** Python und JavaScript sind gleich (sdk/README.md, Regel 6): Ordner, Dateien, Aufrufe, Fehlertypen, READMEs. */

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");

const JS = path.join(__dirname, "..", "platform_sdk");
const PY = path.join(__dirname, "..", "..", "python", "platform_sdk");

const camel = (name) => name.replace(/_([a-z])/g, (_, c) => c.toUpperCase());

/** Dateien unter `dir`, Endung und __init__/index vereinheitlicht. */
function tree(root, dir) {
  const out = [];
  for (const file of fs.readdirSync(path.join(root, dir), { recursive: true })) {
    const full = path.join(root, dir, file);
    if (file.includes("__pycache__") || fs.statSync(full).isDirectory()) continue;
    out.push(file.replace(/__init__\.py$|index\.js$/, "<init>").replace(/\.(py|js)$/, ".<code>"));
  }
  return out.sort();
}

/** Konstanten `NAME = "wert"` (Python) bzw. `const NAME = "wert"` (JavaScript) einer Datei. */
function constants(file, lang) {
  const text = fs.readFileSync(file, "utf-8");
  const re = lang === "py" ? /^([A-Z][A-Z_]+) = "([^"]*)"/gm : /^const ([A-Z][A-Z_]+) = "([^"]*)"/gm;
  return Object.fromEntries([...text.matchAll(re)].map((m) => [m[1], m[2]]));
}

/** Öffentliche Funktionen eines Python-Moduls (ohne _privat), in camelCase. */
function pyFunctions(file) {
  const text = fs.readFileSync(file, "utf-8");
  return [...text.matchAll(/^def ([a-z][a-z0-9_]*)\(/gm)].map((m) => camel(m[1])).sort();
}

/** Öffentliche Methoden einer Python-Klasse (ohne _privat), in camelCase. */
function pyMethods(file, cls) {
  const text = fs.readFileSync(file, "utf-8");
  const body = text.split(`class ${cls}`)[1].split(/^class /m)[0];
  return [...body.matchAll(/^    (?:async )?def ([a-z][a-z0-9_]*)\(/gm)].map((m) => camel(m[1])).sort();
}

function jsMethods(cls) {
  return Object.getOwnPropertyNames(cls.prototype).filter((n) => n !== "constructor" && !n.startsWith("_")).sort();
}

test("gleiche Ordner und Dateien unter adapters/ und common/", () => {
  for (const dir of ["adapters", "common"]) {
    const js = tree(JS, dir).filter((f) => !f.endsWith("connect.js")); // connect.js wird byte-gleich geprüft
    const py = tree(PY, dir).filter((f) => !f.endsWith("connect.js"));
    assert.deepEqual(js, py, dir);
  }
});

test("README, Testdaten und Browser-Skript byte-gleich", () => {
  for (const file of fs.readdirSync(path.join(PY, "adapters"), { recursive: true })) {
    if (!/(README\.md|\.json|connect\.js)$/.test(file)) continue;
    assert.ok(fs.readFileSync(path.join(PY, "adapters", file)).equals(fs.readFileSync(path.join(JS, "adapters", file))), file);
  }
});

test("gleiche Fehlertypen", () => {
  for (const file of ["adapters/bwsync/errors", "adapters/noten/errors", "adapters/transport"]) {
    assert.deepEqual(constants(path.join(JS, `${file}.js`), "js"), constants(path.join(PY, `${file}.py`), "py"), file);
  }
});

test("gleiche Funktionen und Konstanten in paths und common", () => {
  for (const file of ["adapters/bwsync/paths", "common/dates", "common/sizes", "common/downloads"]) {
    const mod = require(path.join(JS, file));
    const jsFns = Object.entries(mod).filter(([, v]) => typeof v === "function").map(([k]) => k).sort();
    assert.deepEqual(jsFns, pyFunctions(path.join(PY, `${file}.py`)), file);
    assert.deepEqual(constants(path.join(JS, `${file}.js`), "js"), constants(path.join(PY, `${file}.py`), "py"), file);
  }
  const { ROUTES, SCRIPT } = require(path.join(JS, "adapters/bwsync/connect"));
  const py = fs.readFileSync(path.join(PY, "adapters/bwsync/connect/server.py"), "utf-8");
  for (const [key, value] of Object.entries(ROUTES)) assert.ok(py.includes(`"${key}": "${value}"`), key);
  assert.ok(py.includes(`SCRIPT = "${SCRIPT}"`));
});

test("gleiche Aufrufe der Clients und Fakes", () => {
  const pairs = [
    ["adapters/bwsync/client", "BwSyncClient"], ["adapters/noten/client", "NotenClient"],
    ["adapters/bwsync/testing", "FakeBwSync"], ["adapters/noten/testing", "FakeNoten"],
  ];
  for (const [file, cls] of pairs) {
    const jsCls = require(path.join(JS, file))[cls];
    assert.deepEqual(jsMethods(jsCls), pyMethods(path.join(PY, `${file}.py`), cls), cls);
  }
});
