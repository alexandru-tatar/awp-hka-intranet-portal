"use strict";

/** Einstellungen aus der Umgebung (06 §2). */

const fs = require("node:fs");

const DEV_REFUSED = "Der Entwicklungsmodus darf nicht in Produktion laufen.";

class Config {
  constructor({ env, slug, basePath, apiUrl, adaptersUrl, issuer, dev, manifest }) {
    this.env = env;
    this.slug = slug;
    this.basePath = basePath;
    this.apiUrl = apiUrl;
    this.adaptersUrl = adaptersUrl;
    this.issuer = issuer;
    this.dev = dev;
    this.manifest = manifest;
    Object.freeze(this);
  }

  static fromEnv(manifestPath = "manifest.json") {
    const e = process.env;
    const env = e.PORTAL_ENV ?? "development";
    const basePath = (e.PORTAL_BASE_PATH ?? "").replace(/\/+$/, "");
    const devRequested = !["", "0"].includes(e.PORTAL_DEV ?? "");
    if (devRequested && (env === "production" || basePath)) {
      throw new Error(DEV_REFUSED);
    }
    const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf-8"));
    return new Config({
      env,
      slug: e.PORTAL_SLUG || manifest.slug,
      basePath,
      apiUrl: (e.PORTAL_API_URL ?? "http://portal-api:8001").replace(/\/+$/, ""),
      adaptersUrl: e.PORTAL_ADAPTERS_URL || (devRequested ? null : "http://portal-adapters:8002"),
      issuer: e.PORTAL_ISSUER ?? "https://portal.hka.example/",
      dev: devRequested,
      manifest,
    });
  }
}

module.exports = { Config, DEV_REFUSED };
