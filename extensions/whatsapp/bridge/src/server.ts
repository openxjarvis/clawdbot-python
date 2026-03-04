/**
 * Baileys Bridge HTTP server entry point.
 *
 * Environment variables:
 *   BRIDGE_PORT    — port to listen on (default: 15000)
 *   BRIDGE_SECRET  — optional shared secret for request authorization
 *   BRIDGE_HOST    — bind address (default: 127.0.0.1)
 */
import express from "express";
import routes from "./routes.js";

const PORT = parseInt(process.env["BRIDGE_PORT"] ?? "15000", 10);
const HOST = process.env["BRIDGE_HOST"] ?? "127.0.0.1";
const SECRET = process.env["BRIDGE_SECRET"] ?? "";

const app = express();
app.use(express.json({ limit: "50mb" }));

// Optional bearer token auth
if (SECRET) {
  app.use((req, res, next) => {
    const auth = req.headers["authorization"] ?? "";
    if (auth === `Bearer ${SECRET}`) {
      next();
      return;
    }
    res.status(401).json({ error: "Unauthorized" });
  });
}

// Health check (unauthenticated)
app.get("/health", (_req, res) => {
  res.json({ ok: true, service: "openclaw-whatsapp-bridge" });
});

app.use("/", routes);

// Global error handler
app.use(
  (
    err: Error,
    _req: express.Request,
    res: express.Response,
    _next: express.NextFunction,
  ) => {
    console.error(`[bridge] Unhandled error: ${String(err)}`);
    res.status(500).json({ error: String(err) });
  },
);

const server = app.listen(PORT, HOST, () => {
  // Signal to the Python parent that the bridge is ready (parsed by monitor.py)
  console.log(`BRIDGE_READY port=${PORT}`);
  console.log(`[bridge] Listening on ${HOST}:${PORT}`);
});

// Graceful shutdown
process.on("SIGTERM", () => {
  console.log("[bridge] SIGTERM received, shutting down");
  server.close(() => process.exit(0));
});

process.on("SIGINT", () => {
  console.log("[bridge] SIGINT received, shutting down");
  server.close(() => process.exit(0));
});
