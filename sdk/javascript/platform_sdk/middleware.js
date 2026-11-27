"use strict";

/** Prüft jede Anfrage vor allen Routen (06 §4) und schreibt eine Logzeile (06 §11). */

const devshim = require("./devshim");
const pages = require("./pages");
const { User, requestContext } = require("./context");
const { VerifyError } = require("./errors");
const { pickLanguage, t } = require("./i18n");
const { verify } = require("./verify");

const ASSERTION_HEADER = "x-portal-assertion";

function logLine(req, res, started, user, requestId) {
  console.log(
    JSON.stringify({
      ts: new Date().toISOString().replace(/\.\d+Z$/, "Z"),
      level: "info",
      event: "request",
      request_id: requestId,
      user_hash: user ? user.hash : null,
      path: req.path,
      status: res.statusCode,
      ms: Math.round(performance.now() - started),
    }),
  );
}

function portalMiddleware(portal) {
  return async (req, res, next) => {
    const started = performance.now();
    const requestId = req.headers["x-request-id"] ?? null;
    const store = { requestId, assertion: null, user: null, language: pickLanguage(req.headers["accept-language"]) };

    await requestContext.run(store, async () => {
      if (req.path === "/healthz" && (req.method === "GET" || req.method === "HEAD")) return next();
      const cfg = portal.config;
      if (cfg.dev && req.path.startsWith("/__dev/")) return next();

      const token = req.headers[ASSERTION_HEADER];
      let user;
      if (cfg.dev && token === undefined) {
        user = devshim.userFromCookie(req);
        if (user === null) return res.redirect(303, "/__dev/login");
      } else {
        const finish = (status, title) => {
          res.on("finish", () => logLine(req, res, started, null, requestId));
          return pages.error(req, res, status, title, t("login_hint"));
        };
        if (token === undefined) return finish(401, t("login_missing_title"));
        let claims;
        try {
          claims = await verify(token, { keys: portal.jwks, issuer: cfg.issuer, audience: cfg.slug });
        } catch (err) {
          if (err instanceof VerifyError) return finish(401, t("login_invalid_title"));
          throw err;
        }
        user = new User({ sub: claims.sub, name: String(claims.name ?? ""), roles: claims.roles, email: claims.email ?? null });
        store.assertion = token;
      }

      store.user = user;
      req.portal = { user, assertion: store.assertion, requestId, language: store.language };
      res.on("finish", () => logLine(req, res, started, user, requestId));
      return next();
    });
  };
}

module.exports = { portalMiddleware, ASSERTION_HEADER };
