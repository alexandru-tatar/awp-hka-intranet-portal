"use strict";

/** Zwischenspeicher für die öffentlichen Schlüssel des Portals (06 §6). */

const crypto = require("node:crypto");

const FRESH_S = 300;
const UNKNOWN_REFETCH_S = 30;
const STALE_MAX_S = 3600;

const nowSeconds = () => Date.now() / 1000;

class JwksCache {
  constructor(url, keys = null) {
    this._url = url;
    this._keys = new Map(Object.entries(keys ?? {}));
    this._fetchedAt = keys ? nowSeconds() : 0;
    this._lastUnknown = -Infinity;
    this._lastWarning = -Infinity;
    this._inflight = null;
  }

  /** Feste Schlüssel ohne Abruf (für Tests). */
  static fixed(keys) {
    const cache = new JwksCache(null, keys);
    cache._fetchedAt = Infinity;
    return cache;
  }

  async get(kid, now = nowSeconds()) {
    const fresh = now - this._fetchedAt < FRESH_S;
    if (this._keys.has(kid) && fresh) return this._keys.get(kid);
    if (!this._keys.has(kid) && now - this._lastUnknown >= UNKNOWN_REFETCH_S) {
      this._lastUnknown = now;
      await this._refetch(now);
    } else if (this._keys.has(kid) && !fresh) {
      await this._refetch(now);
    }
    if (this._keys.has(kid) && now - this._fetchedAt < STALE_MAX_S) return this._keys.get(kid);
    throw new KeyError(kid);
  }

  async _refetch(now) {
    if (this._url === null) return;
    if (this._inflight) {
      await this._inflight; // ein anderer Aufruf holt schon
      return;
    }
    this._inflight = this._load(now).finally(() => {
      this._inflight = null;
    });
    await this._inflight;
  }

  async _load(now) {
    try {
      const response = await fetch(this._url, { signal: AbortSignal.timeout(2000) });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const jwks = await response.json();
      const keys = new Map();
      for (const jwk of jwks.keys ?? []) {
        if (jwk.kid) keys.set(jwk.kid, crypto.createPublicKey({ key: jwk, format: "jwk" }));
      }
      this._keys = keys;
      this._fetchedAt = nowSeconds();
    } catch (err) {
      if (now - this._lastWarning >= 60) {
        this._lastWarning = now;
        console.warn(`JWKS nicht abrufbar: ${err.name}`);
      }
    }
  }
}

/** Unbekannte Schlüsselkennung. */
class KeyError extends Error {}

module.exports = { JwksCache, KeyError };
