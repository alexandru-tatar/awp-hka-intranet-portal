"use strict";

/** Bausteine ohne Netz: Pfadregeln, common/, Fakes, Fehlertypen als Konstanten (wie test_bibliothek.py). */

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const zlib = require("node:zlib");
const { test } = require("node:test");
const { AdapterError } = require("../platform_sdk");
const transport = require("../platform_sdk/adapters/transport");
const { errors, paths, connect } = require("../platform_sdk/adapters/bwsync");
const { FakeBwSync } = require("../platform_sdk/adapters/bwsync/testing");
const { FakeNoten } = require("../platform_sdk/adapters/noten/testing");
const { folder } = require("../platform_sdk/adapters/bwsync/models");
const { dates, downloads, sizes } = require("../platform_sdk/common");

const ROOT = path.join(__dirname, "..", "platform_sdk");
const req = { portal: { assertion: "token", requestId: null, user: { sub: "test-person" } } };

async function rejectsWith(promise, status, type) {
  await assert.rejects(promise, (err) => {
    assert.ok(err instanceof AdapterError);
    assert.deepEqual([err.status, err.type], [status, type]);
    return true;
  });
}

// --- paths ---------------------------------------------------------------------------------------------------

test("validName", () => {
  for (const name of ["a", "Notizen.pdf", "x".repeat(255), 'Ärger "x"', "日本"]) assert.ok(paths.validName(name), name);
  for (const name of ["", ".", "..", "x".repeat(256), " a", "a ", "a/b", "a\\b", "a:b", "50%", "a?", "a#", "a\x00"]) {
    assert.ok(!paths.validName(name), JSON.stringify(name));
  }
});

test("Pfade", () => {
  assert.ok(paths.validPath("") && !paths.validPath("", { root: false }));
  assert.ok(paths.validPath("a/b") && !paths.validPath("a//b") && !paths.validPath("a/../b"));
  assert.ok(!paths.validPath("a/".repeat(600)));
  assert.equal(paths.cleanName("C:\\Users\\x\\Bericht.pdf"), "Bericht.pdf");
  assert.equal(paths.cleanName("../a\x07b"), "ab");
  assert.equal(paths.cleanName(null), "");
  assert.equal(paths.join("", "a"), "a");
  assert.equal(paths.join("a", "b"), "a/b");
  assert.equal(paths.parentOf("a/b/c"), "a/b");
  assert.equal(paths.parentOf("a"), "");
  assert.equal(paths.nameOf("a/b/c"), "c");
  assert.deepEqual(paths.breadcrumbs(""), []);
  assert.deepEqual(paths.breadcrumbs("a/b"), [{ name: "a", path: "a" }, { name: "b", path: "a/b" }]);
});

test("strenges Modell", () => {
  const f = folder({ path: "", truncated: true, skipped: 2, entries: [
    { name: "a", type: "folder", size: null, modified: null },
    { name: "b", type: "file", size: 1, modified: "2026-11-16T13:28:22+00:00" },
    { name: "c", type: "file", size: 1, modified: null },
  ] });
  assert.equal(f.entries.length, 3);
  assert.ok(f.entries[1].modified instanceof Date);
  assert.throws(() => folder({ path: "", entries: [], truncated: false, skipped: 0, extra: 1 }), transport.ContractError);
  assert.throws(() => folder({ path: "", entries: [{ name: "a/b", type: "file" }], truncated: false, skipped: 0 }));
});

// --- common --------------------------------------------------------------------------------------------------

test("sizes", () => {
  assert.deepEqual([null, 0, 1023, 1024, 1_300_000, 5 * 1024 ** 5].map((n) => sizes.formatSize(n)),
    ["–", "0 B", "1023 B", "1,0 KB", "1,2 MB", "5120,0 TB"]);
  assert.equal(sizes.formatSize(null, { empty: "" }), "");
});

test("dates", () => {
  assert.equal(dates.formatDatetime(null), "–");
  assert.equal(dates.formatDatetime(new Date("2026-11-16T13:28:00Z")), "16.11.2026, 14:28");
  assert.equal(dates.formatDatetime("2026-07-01T10:00:00"), "01.07.2026, 12:00"); // ohne Zone: UTC
});

test("contentDisposition", () => {
  for (const [name, ascii] of [['Ärger "x".zip', "Arger x.zip"], ["日本.txt", "download.txt"], ["", "download"], ["a\\b\nc", "abc"]]) {
    const value = downloads.contentDisposition(name);
    assert.ok(value.startsWith(`attachment; filename="${ascii}"; filename*=UTF-8''`), value);
    assert.ok(!value.includes("\n") && value.split('"').length === 3);
  }
  assert.equal(downloads.contentDisposition('Ärger "x".zip'),
    "attachment; filename=\"Arger x.zip\"; filename*=UTF-8''%C3%84rger%20x.zip");
  const headers = downloads.downloadHeaders("a.zip");
  assert.equal(headers["X-Content-Type-Options"], "nosniff");
  assert.equal(headers["Cache-Control"], "no-store");
});

// --- Fehlertypen, Bibliothek ohne Oberfläche ----------------------------------------------------------------

test("Fehlertypen sind Konstanten", () => {
  const kinds = new Set(Object.entries(errors).filter(([, v]) => typeof v === "string").map(([, v]) => v));
  assert.deepEqual(kinds, new Set(["bwsync-not-linked", "bwsync-link-invalid", "bwsync-forbidden", "bwsync-not-found",
    "bwsync-exists", "bwsync-parent-missing", "bwsync-conflict", "bwsync-too-large", "bwsync-locked",
    "bwsync-not-a-file", "bwsync-not-a-folder", "bwsync-move-into-self", "bwsync-folder-too-large",
    "bwsync-link-failed"]));
  assert.deepEqual(errors.LINK_PROBLEMS, new Set([errors.NOT_LINKED, errors.LINK_INVALID]));
  assert.equal(transport.BACKEND_UNAVAILABLE, "backend-unavailable");
});

test("keine Oberfläche unter adapters/ und common/", () => {
  for (const dir of ["adapters", "common"]) {
    for (const file of fs.readdirSync(path.join(ROOT, dir), { recursive: true })) {
      const full = path.join(ROOT, dir, file);
      if (fs.statSync(full).isDirectory()) continue;
      assert.ok([".js", ".json", ".md"].includes(path.extname(file)), file);
      if (file.endsWith(".js") && !file.endsWith("connect.js")) {
        const text = fs.readFileSync(full, "utf-8");
        assert.ok(!text.includes("<div") && !text.includes("<p>") && !text.includes("Bitte "), file);
      }
    }
  }
});

test("connect", () => {
  assert.equal(connect.SCRIPT, "/_sdk/bwsync/connect.js");
  assert.deepEqual(Object.keys(connect.ROUTES).sort(), ["disconnect", "poll", "start", "status"]);
});

// --- Fakes ---------------------------------------------------------------------------------------------------

function unzipNames(buf) {
  const names = [];
  let i = 0;
  while (buf.readUInt32LE(i) === 0x04034b50) {
    const size = buf.readUInt32LE(i + 18);
    const nameLen = buf.readUInt16LE(i + 26);
    const name = buf.subarray(i + 30, i + 30 + nameLen).toString("utf-8");
    const data = zlib.inflateRawSync(buf.subarray(i + 30 + nameLen, i + 30 + nameLen + size));
    names.push([name, data.toString()]);
    i += 30 + nameLen + size;
  }
  return names;
}

test("FakeBwSync verhält sich wie der Adapter", async () => {
  const fake = new FakeBwSync();
  const bwsync = fake.client();
  await bwsync.mkdir(req, "Studium");
  await bwsync.upload(req, "Studium/a b.txt", Buffer.from("hallo"));
  assert.deepEqual((await bwsync.list(req, "Studium")).entries.map((e) => e.name), ["a b.txt"]);
  assert.equal((await bwsync.download(req, "Studium/a b.txt")).toString(), "hallo");
  assert.deepEqual(fake.calls[1], ["PUT", "/bwsync/files/Studium/a b.txt", 5]);
  await rejectsWith(bwsync.mkdir(req, "Studium"), 409, errors.EXISTS);
  await rejectsWith(bwsync.upload(req, "Studium/a b.txt", Buffer.alloc(0)), 412, errors.EXISTS);
  await rejectsWith(bwsync.mkdir(req, "x/y"), 409, errors.PARENT_MISSING);
  await rejectsWith(bwsync.list(req, "fehlt"), 404, errors.NOT_FOUND);
  await rejectsWith(bwsync.move(req, "Studium", "fehlt/x"), 409, errors.PARENT_MISSING);
  await rejectsWith(bwsync.move(req, "Studium", "Studium/x"), 400, errors.MOVE_INTO_SELF);
  await rejectsWith(bwsync.delete(req, "Studium"), 409, errors.NOT_A_FILE);
  await rejectsWith(bwsync.list(req, "Studium/a b.txt"), 409, errors.NOT_A_FOLDER);
  await rejectsWith(bwsync.delete(req, "Studium/a b.txt", { folder: true }), 409, errors.NOT_A_FOLDER);
  await rejectsWith(bwsync.upload(req, "Studium/gross", Buffer.alloc(10 * 1024 * 1024 + 1)), 413, errors.TOO_LARGE);
  await bwsync.mkdir(req, "Archiv");
  await bwsync.move(req, "Studium", "Archiv/Studium");
  assert.deepEqual([...fake.files.keys()], ["Archiv/Studium/a b.txt"]);
  const stream = await bwsync.downloadZip(req, "Archiv");
  const parts = [];
  for await (const part of stream) parts.push(part);
  assert.deepEqual(unzipNames(Buffer.concat(parts)), [["Archiv/Studium/a b.txt", "hallo"]]);
  assert.ok(stream.closed);
  await bwsync.delete(req, "Archiv", { folder: true });
  assert.deepEqual([...fake.folders], [""]);
  assert.equal(fake.files.size, 0);
  await assert.rejects(bwsync.list(req, "../x"), TypeError);
});

test("FakeBwSync: fail, linked, install", async () => {
  const fake = new FakeBwSync();
  const portal = { adapters: { bwsync: "original" } };
  fake.install(portal);
  assert.equal(await portal.adapters.bwsync.isLinked(req), true);
  fake.linked = false;
  assert.equal(await portal.adapters.bwsync.isLinked(req), false);
  await rejectsWith(portal.adapters.bwsync.list(req), 403, errors.NOT_LINKED);
  fake.fail = [503, null];
  await rejectsWith(portal.adapters.bwsync.list(req), 503, transport.BACKEND_UNAVAILABLE);
  fake.uninstall();
  assert.equal(portal.adapters.bwsync, "original");
});

test("Fake ohne Anfrage", async () => {
  await rejectsWith(new FakeBwSync().client().list({}), 500, transport.NO_USER_CONTEXT);
});

test("FakeNoten", async () => {
  const fake = new FakeNoten({ "test-person": [
    { module: "Mathe 1", semester: "WS 2025/26", grade: "1,3", credits: 5 },
    { module: "Info 1", semester: "SS 2026", grade: "bestanden", credits: null },
  ] });
  const noten = fake.client();
  assert.equal((await noten.listMyGrades(req)).items.length, 2);
  assert.deepEqual((await noten.listMyGrades(req, { semester: "SS 2026" })).items.map((g) => g.module), ["Info 1"]);
  fake.fail = [504, transport.BACKEND_TIMEOUT];
  await rejectsWith(noten.listMyGrades(req), 504, transport.BACKEND_TIMEOUT);
});
