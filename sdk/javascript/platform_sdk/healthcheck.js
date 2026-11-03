"use strict";

// Gesundheitstest für den Container (`HEALTHCHECK`): nur Standardbibliothek, Ausgang 0 oder 1.
const port = Number(process.env.PORT || 8080);

fetch(`http://127.0.0.1:${port}/healthz`, { signal: AbortSignal.timeout(2000) })
  .then((res) => process.exit(res.status === 200 ? 0 : 1))
  .catch(() => process.exit(1));
