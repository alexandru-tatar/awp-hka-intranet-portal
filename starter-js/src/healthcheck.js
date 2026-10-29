"use strict";

// Gesundheitstest für den Container (HEALTHCHECK im Dockerfile). Nur Standardbibliothek, kein curl nötig.
const port = Number(process.env.PORT || 8080);

fetch(`http://127.0.0.1:${port}/healthz`, { signal: AbortSignal.timeout(2000) })
  .then((res) => process.exit(res.ok ? 0 : 1))
  .catch(() => process.exit(1));
