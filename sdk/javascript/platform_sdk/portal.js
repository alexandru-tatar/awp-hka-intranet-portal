"use strict";

/** Öffentliche Schnittstelle des SDK (06 §3.1). */

const express = require("express");
const path = require("node:path");
const { Adapters } = require("./adapters");
const { Config } = require("./config");
const devshim = require("./devshim");
const { JwksCache } = require("./jwks");
const { Layout } = require("./layout");
const { portalMiddleware } = require("./middleware");
const pages = require("./pages");

const KIT_DIR = path.join(__dirname, "kit");

class Portal {
  constructor(config) {
    this.config = config;
    this.basePath = config.basePath;
    this.manifest = config.manifest;
    this.jwks = new JwksCache(`${config.apiUrl}/.well-known/jwks.json`);
    this.adapters = new Adapters(config);
    this._layout = new Layout(config);
  }

  static fromEnv(manifestPath = "manifest.json") {
    return new Portal(Config.fromEnv(manifestPath));
  }

  /** Prüfung der Anmeldung vor allen Routen, /healthz und im Entwicklungsmodus die Test-Anmeldung. */
  install(app) {
    app.use(portalMiddleware(this));
    app.get("/healthz", (_req, res) => {
      res.json({ status: "ok" });
    });
    if (this.config.dev) {
      // kit/ legt erst `make sdk-release` an; in den SDK-Tests fehlt es
      app.use("/__dev/kit", express.static(KIT_DIR));
      app.use("/__dev", devshim.router(this));
    }
  }

  /** Router der App; die App hängt ihn unter `portal.url("/")` ein. */
  router() {
    return express.Router();
  }

  /** Schützt eine Route für die genannten Rollen (403 sonst). Die Person steht in `req.portal.user`. */
  requires(...roles) {
    return (req, res, next) => {
      const user = req.portal?.user;
      if (!user) {
        return pages.error(req, res, 401, "Anmeldung fehlt", "Bitte melden Sie sich im Portal an.");
      }
      if (!user.roles.some((r) => roles.includes(r))) {
        return pages.error(req, res, 403, "Kein Zugriff", "Diese Seite ist für Ihre Rolle nicht freigegeben.");
      }
      return next();
    };
  }

  url(pathName) {
    if (!pathName.startsWith("/")) {
      throw new Error("portal.url() erwartet einen Pfad, der mit „/“ beginnt.");
    }
    return this.basePath + pathName;
  }

  async layout({ title, body, current, user }) {
    return this._layout.render({ title, body, current, user });
  }
}

module.exports = { Portal };
