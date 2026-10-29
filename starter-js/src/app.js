"use strict";

const express = require("express");

/**
 * Erzeugt die Express-App.
 * Getrennt von server.js, damit Tests ohne festen Port laufen.
 */
function createApp() {
  const app = express();
  app.disable("x-powered-by");

  // Health-Endpunkt: wird vom Container-Gesundheitstest und von der Plattform abgefragt.
  app.get("/healthz", (_req, res) => {
    res.status(200).json({ status: "ok" });
  });

  return app;
}

module.exports = { createApp };
