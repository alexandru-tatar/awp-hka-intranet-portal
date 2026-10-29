"use strict";

const { createApp } = require("./app");

const port = Number(process.env.PORT || 8080);
const server = createApp().listen(port, "0.0.0.0", () => {
  console.log(JSON.stringify({ event: "listening", port }));
});

// Geordnetes Beenden, damit der Container bei "stop" nicht abgebrochen wird.
function shutdown() {
  server.close(() => process.exit(0));
}
process.on("SIGTERM", shutdown);
process.on("SIGINT", shutdown);
