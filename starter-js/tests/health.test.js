"use strict";

const { createApp } = require("../src/app");

let server;
let base;

beforeAll(async () => {
  await new Promise((resolve) => {
    server = createApp().listen(0, "127.0.0.1", resolve);
  });
  base = `http://127.0.0.1:${server.address().port}`;
});

afterAll(async () => {
  await new Promise((resolve) => server.close(resolve));
});

test("GET /healthz antwortet mit 200 und status ok", async () => {
  const res = await fetch(`${base}/healthz`);
  expect(res.status).toBe(200);
  expect(await res.json()).toEqual({ status: "ok" });
});

test("ein unbekannter Pfad liefert 404", async () => {
  const res = await fetch(`${base}/gibt-es-nicht`);
  expect(res.status).toBe(404);
});
