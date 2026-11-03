"use strict";

/**
 * Seitenrahmen des Portals (04 §8, 06 §7).
 *
 * Betrieb: Menü von `GET {PORTAL_API_URL}/nav`, Kit-Name aus dem Header `X-Portal-Kit`.
 * Entwicklung oder Menü nicht erreichbar: Menü aus dem eigenen Manifest.
 * Eigenes CSS der App wird immer als `{basePath}/static/app.css` eingebunden.
 */

const { currentAssertion } = require("./context");
const { env } = require("./templates");

class Layout {
  constructor(config) {
    this.config = config;
    this._kit = "kit"; // zuletzt bekannter Kit-Name, damit der Ersatz-Rahmen gestaltet bleibt
  }

  async render({ title, body, current, user }) {
    const cfg = this.config;
    let navHtml = null;
    let kit;
    if (cfg.dev) {
      kit = { css: "/__dev/kit/kit.css", js: "/__dev/kit/kit.js", icons: "/__dev/kit/icons.svg" };
    } else {
      navHtml = await this._fetchNav();
      kit = {
        css: `/_portal/static/${this._kit}.css`,
        js: `/_portal/static/${this._kit}.js`,
        icons: "/_portal/static/icons.svg",
      };
    }
    if (navHtml === null) navHtml = env.render("nav.html", { item: this._menuItem(), current, kit });
    return env.render("layout.html", {
      title,
      body, // Inhalt kommt aus einer Vorlage mit autoescape
      nav_html: navHtml, // vom Portal oder aus nav.html
      user,
      kit,
      app_css: `${cfg.basePath}/static/app.css`,
      dev: cfg.dev,
    });
  }

  _menuItem() {
    const m = this.config.manifest;
    return { category: m.category, label: m.menu.label, icon: m.menu.icon, path: this.config.basePath || "/" };
  }

  async _fetchNav() {
    const token = currentAssertion();
    if (token === null) return null;
    try {
      const response = await fetch(`${this.config.apiUrl}/nav`, {
        headers: { "X-Portal-Assertion": token },
        signal: AbortSignal.timeout(2000),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      this._kit = response.headers.get("x-portal-kit") ?? this._kit;
      return await response.text();
    } catch (err) {
      console.warn(`Menü nicht abrufbar, Ersatz-Menü: ${err.name}`);
      return null;
    }
  }
}

module.exports = { Layout };
