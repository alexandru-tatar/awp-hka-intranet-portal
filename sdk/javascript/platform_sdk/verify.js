"use strict";

/** Prüfung der Portal-Assertion (06 §5). */

const crypto = require("node:crypto");
const { VerifyError } = require("./errors");
const { KeyError } = require("./jwks");

const MAX_TOKEN_BYTES = 8192;
const LEEWAY_S = 5;

function decodePart(part) {
  try {
    const value = JSON.parse(Buffer.from(part, "base64url").toString("utf-8"));
    return value !== null && typeof value === "object" && !Array.isArray(value) ? value : null;
  } catch {
    return null;
  }
}

async function verify(token, { keys, issuer, audience, now = Date.now() / 1000 }) {
  if (!token || token.length > MAX_TOKEN_BYTES || token.split(".").length !== 3) {
    throw new VerifyError("Malformed");
  }
  const [encodedHeader, encodedPayload, encodedSignature] = token.split(".");
  const header = decodePart(encodedHeader);
  if (header === null) throw new VerifyError("Malformed");
  if (header.alg !== "RS256") throw new VerifyError("BadAlgorithm");
  const kid = header.kid;
  if (!kid || typeof kid !== "string") throw new VerifyError("MissingKid");
  let key;
  try {
    key = await keys.get(kid, now);
  } catch (err) {
    if (err instanceof KeyError) throw new VerifyError("UnknownKey");
    throw err;
  }
  const signedData = Buffer.from(`${encodedHeader}.${encodedPayload}`);
  let valid = false;
  try {
    valid = crypto.verify("RSA-SHA256", signedData, key, Buffer.from(encodedSignature, "base64url"));
  } catch {
    valid = false;
  }
  if (!valid) throw new VerifyError("BadSignature");
  const claims = decodePart(encodedPayload);
  if (claims === null) throw new VerifyError("Malformed");

  if (claims.iss !== issuer) throw new VerifyError("WrongIssuer");
  const aud = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
  if (!aud.includes(audience)) throw new VerifyError("WrongAudience");
  if (claims.v !== 1) throw new VerifyError("UnsupportedVersion");
  const { exp, iat } = claims;
  if (typeof exp !== "number" || !(exp >= now - LEEWAY_S)) throw new VerifyError("Expired");
  if (typeof iat !== "number" || !(iat <= now + LEEWAY_S)) throw new VerifyError("NotYetValid");
  if (typeof claims.sub !== "string" || !claims.sub) throw new VerifyError("MissingSubject");
  if (!Array.isArray(claims.roles) || !claims.roles.every((r) => typeof r === "string")) {
    throw new VerifyError("BadRoles");
  }
  return claims;
}

module.exports = { verify, MAX_TOKEN_BYTES, LEEWAY_S };
