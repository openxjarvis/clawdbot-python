/**
 * Express REST API routes for the Baileys bridge.
 * Exposes session management, QR, status, send, react, poll, logout.
 */
import { Router } from "express";
import {
  createSession,
  getAllSessions,
  getSession,
  logoutSession,
  markMessagesRead,
  sendPollMessage,
  sendReactionMessage,
  sendTextMessage,
} from "./session.js";

const router = Router();

// ----- Sessions -----

/** POST /sessions — Start a new session or reconnect */
router.post("/sessions", async (req, res) => {
  const { accountId, authDir, eventWebhookUrl } = req.body as {
    accountId?: string;
    authDir?: string;
    eventWebhookUrl?: string;
  };

  if (!accountId || typeof accountId !== "string") {
    res.status(400).json({ error: "accountId is required" });
    return;
  }
  if (!eventWebhookUrl || typeof eventWebhookUrl !== "string") {
    res.status(400).json({ error: "eventWebhookUrl is required" });
    return;
  }

  try {
    const session = await createSession({ accountId, authDir, eventWebhookUrl });
    res.json({
      sessionId: accountId,
      state: session.state,
      selfJid: session.selfJid,
      selfE164: session.selfE164,
    });
  } catch (err) {
    console.error(`[bridge] Failed to create session ${accountId}: ${String(err)}`);
    res.status(500).json({ error: String(err) });
  }
});

/** GET /sessions — List all active sessions */
router.get("/sessions", (_req, res) => {
  const list = getAllSessions().map((s) => ({
    sessionId: s.accountId,
    state: s.state,
    selfJid: s.selfJid,
    selfE164: s.selfE164,
    hasQr: Boolean(s.qrDataUrl),
  }));
  res.json({ sessions: list });
});

/** DELETE /sessions/:id — Disconnect and remove session */
router.delete("/sessions/:id", async (req, res) => {
  const { id } = req.params;
  const session = getSession(id!);
  if (!session) {
    res.status(404).json({ error: "Session not found" });
    return;
  }
  await session.stop();
  res.json({ ok: true });
});

// ----- QR -----

/**
 * GET /sessions/:id/qr
 * Returns { qr: "<png-base64-data-url>" } or 202 if QR not yet available.
 */
router.get("/sessions/:id/qr", (req, res) => {
  const { id } = req.params;
  const session = getSession(id!);
  if (!session) {
    res.status(404).json({ error: "Session not found" });
    return;
  }
  if (!session.qrDataUrl) {
    res.status(202).json({ status: "pending", state: session.state });
    return;
  }
  res.json({ qr: session.qrDataUrl });
});

// ----- Status -----

/** GET /sessions/:id/status */
router.get("/sessions/:id/status", (req, res) => {
  const { id } = req.params;
  const session = getSession(id!);
  if (!session) {
    res.status(404).json({ error: "Session not found" });
    return;
  }
  res.json({
    state: session.state,
    selfJid: session.selfJid,
    selfE164: session.selfE164,
    hasQr: Boolean(session.qrDataUrl),
  });
});

// ----- Send -----

/**
 * POST /sessions/:id/send
 * Body: { to: string, text: string, replyTo?: string }
 */
router.post("/sessions/:id/send", async (req, res) => {
  const { id } = req.params;
  const { to, text, replyTo } = req.body as {
    to?: string;
    text?: string;
    replyTo?: string;
  };

  if (!to || !text) {
    res.status(400).json({ error: "to and text are required" });
    return;
  }

  try {
    const result = await sendTextMessage(id!, to, text, replyTo);
    res.json(result);
  } catch (err) {
    console.error(`[bridge] Send error for ${id}: ${String(err)}`);
    res.status(500).json({ error: String(err) });
  }
});

/**
 * POST /sessions/:id/send_media
 * Body: { to: string, mediaBase64: string, mimeType: string, caption?: string, fileName?: string }
 */
router.post("/sessions/:id/send_media", async (req, res) => {
  const { id } = req.params;
  const { to, mediaBase64, mimeType, caption, fileName } = req.body as {
    to?: string;
    mediaBase64?: string;
    mimeType?: string;
    caption?: string;
    fileName?: string;
  };

  if (!to || !mediaBase64 || !mimeType) {
    res.status(400).json({ error: "to, mediaBase64, and mimeType are required" });
    return;
  }

  const session = getSession(id!);
  if (!session?.socket) {
    res.status(404).json({ error: "Session not found or not active" });
    return;
  }

  try {
    const buffer = Buffer.from(mediaBase64, "base64");
    const jid = toWaJid(to);
    let content: Parameters<typeof session.socket.sendMessage>[1];

    if (mimeType.startsWith("image/")) {
      content = { image: buffer, caption: caption ?? "" };
    } else if (mimeType.startsWith("video/")) {
      content = { video: buffer, caption: caption ?? "" };
    } else if (mimeType.startsWith("audio/")) {
      const audioMime = mimeType === "audio/ogg" ? "audio/ogg; codecs=opus" : mimeType;
      content = { audio: buffer, mimetype: audioMime, ptt: true };
    } else {
      content = {
        document: buffer,
        mimetype: mimeType,
        fileName: fileName ?? "file",
        caption: caption ?? "",
      };
    }

    const result = await session.socket.sendMessage(jid, content);
    const messageId = (result as { key?: { id?: string } })?.key?.id ?? "unknown";
    res.json({ messageId });
  } catch (err) {
    console.error(`[bridge] Send media error for ${id}: ${String(err)}`);
    res.status(500).json({ error: String(err) });
  }
});

// ----- React -----

/**
 * POST /sessions/:id/react
 * Body: { to: string, messageId: string, emoji: string, remove?: boolean, fromMe?: boolean }
 */
router.post("/sessions/:id/react", async (req, res) => {
  const { id } = req.params;
  const { to, messageId, emoji, remove, fromMe } = req.body as {
    to?: string;
    messageId?: string;
    emoji?: string;
    remove?: boolean;
    fromMe?: boolean;
  };

  if (!to || !messageId) {
    res.status(400).json({ error: "to and messageId are required" });
    return;
  }

  try {
    const reactionEmoji = remove ? "" : (emoji ?? "");
    await sendReactionMessage(id!, to, messageId, reactionEmoji, fromMe ?? false);
    res.json({ ok: true });
  } catch (err) {
    console.error(`[bridge] React error for ${id}: ${String(err)}`);
    res.status(500).json({ error: String(err) });
  }
});

// ----- Poll -----

/**
 * POST /sessions/:id/poll
 * Body: { to: string, question: string, options: string[], maxSelections?: number }
 */
router.post("/sessions/:id/poll", async (req, res) => {
  const { id } = req.params;
  const { to, question, options, maxSelections } = req.body as {
    to?: string;
    question?: string;
    options?: string[];
    maxSelections?: number;
  };

  if (!to || !question || !Array.isArray(options) || options.length === 0) {
    res.status(400).json({ error: "to, question, and options[] are required" });
    return;
  }

  try {
    const result = await sendPollMessage(id!, to, question, options, maxSelections ?? 1);
    res.json(result);
  } catch (err) {
    console.error(`[bridge] Poll error for ${id}: ${String(err)}`);
    res.status(500).json({ error: String(err) });
  }
});

// ----- Mark Read -----

/**
 * POST /sessions/:id/read
 * Body: { keys: Array<{ remoteJid, id, participant?, fromMe? }> }
 */
router.post("/sessions/:id/read", async (req, res) => {
  const { id } = req.params;
  const { keys } = req.body as {
    keys?: Array<{ remoteJid: string; id: string; participant?: string; fromMe?: boolean }>;
  };

  if (!Array.isArray(keys)) {
    res.status(400).json({ error: "keys[] is required" });
    return;
  }

  try {
    await markMessagesRead(id!, keys);
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: String(err) });
  }
});

// ----- Logout -----

/** POST /sessions/:id/logout */
router.post("/sessions/:id/logout", async (req, res) => {
  const { id } = req.params;
  try {
    await logoutSession(id!);
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: String(err) });
  }
});

function toWaJid(input: string): string {
  const trimmed = input.trim();
  if (trimmed.includes("@")) return trimmed;
  const digits = trimmed.replace(/\D/g, "");
  return `${digits}@s.whatsapp.net`;
}

export default router;
