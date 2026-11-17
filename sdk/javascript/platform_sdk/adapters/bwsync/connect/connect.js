// Portal-SDK: bwSync&Share-Konto verbinden (Nextcloud Login Flow v2) und trennen. Ohne Oberfläche und ohne Texte.
// Spricht nur mit dem Gateway (gleiche Herkunft, Cookie der Sitzung). App-Passwort und Poll-Token bleiben im
// Adapter; das Skript sieht nur login_url (Anmeldeseite von bwSync&Share) und den Zustand.
// Einbinden: <script src="{{ portal.url('/_sdk/bwsync/connect.js') }}" defer></script>, danach window.PortalBwSync.
// Beschreibung: platform_sdk/adapters/bwsync/README.md, Abschnitt „Konto verbinden“.
(function () {
  "use strict";

  var ROUTES = Object.freeze({
    status: "/connect/bwsync",
    start: "/connect/bwsync/start",
    poll: "/connect/bwsync/poll",
    disconnect: "/connect/bwsync",
  });
  // Fehlertypen, die das Skript selbst meldet; sonst kommt der type des Gateways/Adapters (z. B. bwsync-...).
  var ERRORS = Object.freeze({
    POPUP_BLOCKED: "connect-popup-blocked",
    EXPIRED: "connect-expired",
    ABORTED: "connect-aborted",
    SESSION_EXPIRED: "portal-session-expired",
    UNAVAILABLE: "backend-unavailable",
  });
  var POLL_MS = 3000;

  async function call(method, url) {
    var response;
    try {
      response = await fetch(url, {
        method: method,
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
    } catch (e) {
      return { ok: false, status: 0, body: {} };
    }
    var body = {};
    try {
      body = await response.json();
    } catch (e) {
      body = {};
    }
    if (!body || typeof body !== "object") body = {};
    return { ok: response.ok, status: response.status, body: body };
  }

  function problem(result) {
    if (result.status === 401) return { type: ERRORS.SESSION_EXPIRED, status: 401 };
    var type = typeof result.body.type === "string" ? result.body.type.replace(/^urn:hka:problem:/, "") : "";
    return { type: type || ERRORS.UNAVAILABLE, status: result.status };
  }

  /**
   * Verbinden. Direkt im Klick-Handler aufrufen (sonst blockiert der Browser den neuen Tab).
   * onState bekommt {state: "waiting"}, dann {state: "linked", account} oder {state: "error", type, status}.
   * Rückgabe: {cancel()} zum Abbrechen des Wartens.
   */
  function connect(onState) {
    var cancelled = false;
    var tab = window.open("", "_blank");
    if (!tab) {
      onState({ state: "error", type: ERRORS.POPUP_BLOCKED, status: 0 });
      return { cancel: function () {} };
    }
    tab.opener = null; // die Anmeldeseite bekommt keinen Zugriff auf diese Seite
    onState({ state: "waiting" });

    function fail(error) {
      if (!cancelled) onState({ state: "error", type: error.type, status: error.status });
    }

    async function poll(until) {
      if (cancelled) return;
      if (Date.now() > until) return fail({ type: ERRORS.EXPIRED, status: 0 });
      await new Promise(function (resolve) { setTimeout(resolve, POLL_MS); });
      if (cancelled) return;
      var result = await call("POST", ROUTES.poll);
      if (result.status === 0) return poll(until); // kurz nicht erreichbar: weiter warten
      if (!result.ok) return fail(problem(result));
      if (result.body.state === "linked") {
        if (!cancelled) onState({ state: "linked", account: result.body.account || null });
        return undefined;
      }
      if (result.body.state === "pending") return poll(until);
      return fail({ type: ERRORS.ABORTED, status: result.status });
    }

    (async function () {
      var started = await call("POST", ROUTES.start);
      var url = started.body.login_url;
      if (!started.ok || typeof url !== "string" || url.indexOf("https://") !== 0) {
        tab.close();
        return fail(started.ok ? { type: ERRORS.UNAVAILABLE, status: started.status } : problem(started));
      }
      tab.location.href = url;
      return poll(Date.now() + 1000 * (Number(started.body.expires_in) || 1200));
    })();

    return { cancel: function () { cancelled = true; } };
  }

  /** Trennen. Ergebnis {linked: false, revoked: true|null|false}; Fehler als {type, status} (Promise abgelehnt). */
  async function disconnect() {
    var result = await call("DELETE", ROUTES.disconnect);
    if (!result.ok) throw problem(result);
    return { linked: false, revoked: result.body.revoked === undefined ? false : result.body.revoked };
  }

  /** Zustand {linked, account}; Fehler als {type, status} (Promise abgelehnt). */
  async function status() {
    var result = await call("GET", ROUTES.status);
    if (!result.ok) throw problem(result);
    return { linked: result.body.linked === true, account: result.body.account || null };
  }

  window.PortalBwSync = Object.freeze({
    connect: connect,
    disconnect: disconnect,
    status: status,
    ERRORS: ERRORS,
    ROUTES: ROUTES,
  });
})();
