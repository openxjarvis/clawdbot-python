/**
 * Baileys session factory with reconnect policy and event forwarding.
 * Mirrors TypeScript openclaw src/web/session.ts and src/web/reconnect.ts
 */
import {
  DisconnectReason,
  downloadMediaMessage,
  fetchLatestBaileysVersion,
  isJidGroup,
  makeCacheableSignalKeyStore,
  makeWASocket,
} from "@whiskeysockets/baileys";
import pino from "pino";
import qrcode from "qrcode";
import { clearAuth, hasAuth, loadAuthState, resolveAuthDir, safeSaveCreds } from "./auth.js";

export type SessionState = "connecting" | "open" | "closed" | "logged_out";

export interface Session {
  accountId: string;
  authDir: string;
  state: SessionState;
  selfJid: string | null;
  selfE164: string | null;
  qrDataUrl: string | null;
  socket: ReturnType<typeof makeWASocket> | null;
  stop: () => Promise<void>;
}

// ----- Reconnect policy mirrors src/web/reconnect.ts -----
interface BackoffPolicy {
  initialMs: number;
  maxMs: number;
  factor: number;
  jitter: number;
  maxAttempts: number;
}

const DEFAULT_RECONNECT: BackoffPolicy = {
  initialMs: 2_000,
  maxMs: 30_000,
  factor: 1.8,
  jitter: 0.25,
  maxAttempts: 12,
};

function computeBackoff(policy: BackoffPolicy, attempt: number): number {
  const base = Math.min(policy.initialMs * Math.pow(policy.factor, attempt), policy.maxMs);
  const jit = base * policy.jitter * (Math.random() * 2 - 1);
  return Math.max(0, Math.round(base + jit));
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ----- Event forwarding to Python webhook -----
async function postEvent(webhookUrl: string, event: Record<string, unknown>): Promise<void> {
  try {
    await fetch(webhookUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(event),
    });
  } catch (err) {
    console.warn(`[bridge] Failed posting event to ${webhookUrl}: ${String(err)}`);
  }
}

// Global sessions registry
const sessions = new Map<string, Session>();

export function getSession(accountId: string): Session | undefined {
  return sessions.get(accountId);
}

export function getAllSessions(): Session[] {
  return Array.from(sessions.values());
}

// Serializable message payload (strip functions and large objects)
function serializeMessage(msg: Record<string, unknown>): Record<string, unknown> {
  const safe = JSON.parse(
    JSON.stringify(msg, (_key, value) => {
      if (typeof value === "function") return undefined;
      if (typeof value === "bigint") return value.toString();
      return value;
    }),
  );
  return safe;
}

function jidToE164(jid: string): string | null {
  try {
    const bare = jid.split(":")[0]!.split("@")[0]!;
    if (!/^\d+$/.test(bare)) return null;
    return `+${bare}`;
  } catch {
    return null;
  }
}

/**
 * Start a Baileys session for the given accountId.
 * Handles QR generation, reconnect, and event forwarding.
 */
export async function createSession(params: {
  accountId: string;
  authDir?: string;
  eventWebhookUrl: string;
}): Promise<Session> {
  const { accountId, eventWebhookUrl } = params;
  const authDir = resolveAuthDir(accountId, params.authDir);

  // Tear down existing session if any
  const existing = sessions.get(accountId);
  if (existing) {
    await existing.stop();
  }

  const session: Session = {
    accountId,
    authDir,
    state: "connecting",
    selfJid: null,
    selfE164: null,
    qrDataUrl: null,
    socket: null,
    stop: async () => {}, // replaced below
  };
  sessions.set(accountId, session);

  let stopped = false;
  let reconnectAttempt = 0;
  let credsSaveQueue: Promise<void> = Promise.resolve();

  const pinoLogger = pino({ level: "silent" });

  const doConnect = async (): Promise<void> => {
    if (stopped) return;
    session.state = "connecting";
    session.qrDataUrl = null;

    const { state: authState, saveCreds } = await loadAuthState(authDir);
    const { version } = await fetchLatestBaileysVersion();

    const sock = makeWASocket({
      auth: {
        creds: authState.creds,
        keys: makeCacheableSignalKeyStore(authState.keys, pinoLogger),
      },
      version,
      logger: pinoLogger,
      printQRInTerminal: false,
      browser: ["openclaw", "cli", "1.0.0"],
      syncFullHistory: false,
      markOnlineOnConnect: false,
    });

    session.socket = sock;

    // Save credentials on update
    sock.ev.on("creds.update", () => {
      credsSaveQueue = credsSaveQueue
        .then(() => safeSaveCreds(authDir, saveCreds))
        .catch((err) => console.warn(`[bridge] Creds save queue error: ${String(err)}`));
    });

    sock.ev.on("connection.update", async (update) => {
      const { connection, lastDisconnect, qr } = update;

      if (qr) {
        try {
          const dataUrl = await qrcode.toDataURL(qr);
          session.qrDataUrl = dataUrl;
          void postEvent(eventWebhookUrl, {
            type: "qr",
            accountId,
            qr: dataUrl,
          });
        } catch (err) {
          console.warn(`[bridge] QR generation failed: ${String(err)}`);
        }
      }

      if (connection === "open") {
        session.state = "open";
        session.qrDataUrl = null;
        reconnectAttempt = 0;
        const jid = sock.user?.id ?? null;
        session.selfJid = jid;
        session.selfE164 = jid ? jidToE164(jid) : null;
        void postEvent(eventWebhookUrl, {
          type: "connection",
          accountId,
          state: "open",
          selfJid: session.selfJid,
          selfE164: session.selfE164,
        });
        console.log(`[bridge] Session ${accountId} connected (${session.selfE164 ?? session.selfJid})`);
      }

      if (connection === "close") {
        const statusCode = (lastDisconnect?.error as { output?: { statusCode?: number } } | undefined)
          ?.output?.statusCode;
        const isLoggedOut = statusCode === DisconnectReason.loggedOut;

        session.state = isLoggedOut ? "logged_out" : "closed";
        void postEvent(eventWebhookUrl, {
          type: "connection",
          accountId,
          state: session.state,
          statusCode,
        });

        if (isLoggedOut) {
          console.log(`[bridge] Session ${accountId} logged out`);
          return;
        }

        if (stopped) return;

        if (reconnectAttempt >= DEFAULT_RECONNECT.maxAttempts) {
          console.warn(`[bridge] Session ${accountId} max reconnect attempts reached`);
          return;
        }

        const delay = computeBackoff(DEFAULT_RECONNECT, reconnectAttempt++);
        console.log(`[bridge] Session ${accountId} reconnecting in ${delay}ms (attempt ${reconnectAttempt})`);
        await sleep(delay);
        void doConnect().catch((err) =>
          console.error(`[bridge] Reconnect error for ${accountId}: ${String(err)}`),
        );
      }
    });

    // Forward inbound messages to Python (with media download)
    sock.ev.on("messages.upsert", async (upsert: { type?: string; messages?: unknown[] }) => {
      if (upsert.type !== "notify" && upsert.type !== "append") return;
      for (const rawMsg of upsert.messages ?? []) {
        try {
          const msg = rawMsg as Record<string, unknown>;
          const remoteJid = (msg as { key?: { remoteJid?: string } }).key?.remoteJid;
          if (!remoteJid) continue;
          if (remoteJid.endsWith("@status") || remoteJid.endsWith("@broadcast")) continue;

          // Attempt to download media inline (mirrors TS downloadMediaMessage())
          const msgContent = (msg as { message?: Record<string, unknown> }).message ?? {};
          const mediaKey = Object.keys(msgContent).find(
            (k) => k.endsWith("Message") && ["imageMessage", "videoMessage", "audioMessage", "documentMessage", "stickerMessage"].includes(k)
          );
          if (mediaKey && upsert.type === "notify") {
            try {
              const mediaBuffer = await downloadMediaMessage(
                rawMsg as Parameters<typeof downloadMediaMessage>[0],
                "buffer",
                {},
              );
              if (mediaBuffer) {
                const b64 = (mediaBuffer as Buffer).toString("base64");
                (msgContent as Record<string, Record<string, unknown>>)[mediaKey]!["_mediaData"] = b64;
              }
            } catch (mediaErr) {
              console.warn(`[bridge] Media download failed for ${remoteJid}: ${String(mediaErr)}`);
            }
          }

          const serialized = serializeMessage(msg);
          void postEvent(eventWebhookUrl, {
            type: "message",
            accountId,
            upsertType: upsert.type,
            data: serialized,
            selfJid: session.selfJid,
            selfE164: session.selfE164,
            group: isJidGroup(remoteJid),
          });
        } catch (err) {
          console.warn(`[bridge] Error serializing inbound message: ${String(err)}`);
        }
      }
    });

    // Forward messages.update events (reactions, poll votes, read receipts, etc.)
    sock.ev.on("messages.update", async (updates: unknown[]) => {
      for (const update of updates) {
        try {
          const u = update as Record<string, unknown>;
          const key = u["key"] as { remoteJid?: string } | undefined;
          if (!key?.remoteJid) continue;
          if (key.remoteJid.endsWith("@status") || key.remoteJid.endsWith("@broadcast")) continue;

          void postEvent(eventWebhookUrl, {
            type: "message_update",
            accountId,
            data: serializeMessage(u),
            selfJid: session.selfJid,
            selfE164: session.selfE164,
            group: isJidGroup(key.remoteJid),
          });
        } catch (err) {
          console.warn(`[bridge] Error forwarding messages.update: ${String(err)}`);
        }
      }
    });

    // Handle WebSocket-level errors
    if (sock.ws && typeof (sock.ws as unknown as { on?: unknown }).on === "function") {
      (sock.ws as unknown as { on: (event: string, handler: (err: Error) => void) => void }).on(
        "error",
        (err: Error) => console.warn(`[bridge] WebSocket error for ${accountId}: ${String(err)}`),
      );
    }
  };

  session.stop = async () => {
    stopped = true;
    sessions.delete(accountId);
    try {
      session.socket?.ws?.close();
    } catch { /* ignore */ }
    session.state = "closed";
  };

  await doConnect();
  return session;
}

export async function sendTextMessage(
  accountId: string,
  to: string,
  text: string,
  replyToId?: string,
): Promise<{ messageId: string }> {
  const session = getSession(accountId);
  if (!session?.socket) throw new Error(`Session ${accountId} not active`);

  const jid = toWaJid(to);
  const content: Record<string, unknown> = { text };
  if (replyToId) {
    content["contextInfo"] = { stanzaId: replyToId };
  }
  const result = await session.socket.sendMessage(jid, content as Parameters<typeof session.socket.sendMessage>[1]);
  const messageId = (result as { key?: { id?: string } })?.key?.id ?? "unknown";
  return { messageId };
}

export async function sendReactionMessage(
  accountId: string,
  to: string,
  reactionMsgId: string,
  emoji: string,
  fromMe: boolean = false,
): Promise<void> {
  const session = getSession(accountId);
  if (!session?.socket) throw new Error(`Session ${accountId} not active`);

  const jid = toWaJid(to);
  await session.socket.sendMessage(jid, {
    react: {
      text: emoji,
      key: { remoteJid: jid, id: reactionMsgId, fromMe },
    },
  });
}

export async function sendPollMessage(
  accountId: string,
  to: string,
  question: string,
  options: string[],
  maxSelections: number = 1,
): Promise<{ messageId: string }> {
  const session = getSession(accountId);
  if (!session?.socket) throw new Error(`Session ${accountId} not active`);

  const jid = toWaJid(to);
  const result = await session.socket.sendMessage(jid, {
    poll: {
      name: question,
      values: options.slice(0, 12),
      selectableCount: maxSelections,
    },
  });
  const messageId = (result as { key?: { id?: string } })?.key?.id ?? "unknown";
  return { messageId };
}

export async function markMessagesRead(
  accountId: string,
  keys: Array<{ remoteJid: string; id: string; participant?: string; fromMe?: boolean }>,
): Promise<void> {
  const session = getSession(accountId);
  if (!session?.socket) return;
  try {
    await session.socket.readMessages(keys);
  } catch { /* best-effort */ }
}

export async function logoutSession(accountId: string): Promise<void> {
  const session = getSession(accountId);
  if (session?.socket) {
    try {
      await session.socket.logout();
    } catch { /* ignore */ }
  }
  await clearAuth(resolveAuthDir(accountId));
  sessions.delete(accountId);
}

/** Convert E.164 or bare number to WhatsApp JID. */
function toWaJid(input: string): string {
  const trimmed = input.trim();
  if (trimmed.includes("@")) return trimmed;
  const digits = trimmed.replace(/\D/g, "");
  return `${digits}@s.whatsapp.net`;
}

export { hasAuth };
