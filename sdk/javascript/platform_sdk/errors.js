"use strict";

/**
 * Fehler einer Schnittstelle.
 *
 * Die App entscheidet anhand von `type` (Konstanten in `adapters/<system>/errors` und `adapters/transport`) und
 * `status`, nie anhand eines Textes, und schreibt den Text für die Person selbst. `detail` ist für Logs und
 * Fehlersuche (Text des Adapters; leer, wenn keine Antwort vom Adapter kam).
 */
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
