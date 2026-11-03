"use strict";

/** Fehler einer Schnittstelle (06 §8). `detail` ist deutsch und darf angezeigt werden. */
class AdapterError extends Error {
  constructor(status, type, detail, requestId = null) {
    super(`${status} ${type}`);
    this.name = "AdapterError";
    this.status = status;
    this.type = type;
    this.detail = detail;
    this.requestId = requestId;
  }
}

/** Prüfung der Anmeldung fehlgeschlagen (06 §5). `code` nennt den Grund, nie den Token-Inhalt. */
class VerifyError extends Error {
  constructor(code) {
    super(code);
    this.name = "VerifyError";
    this.code = code;
  }
}

module.exports = { AdapterError, VerifyError };
