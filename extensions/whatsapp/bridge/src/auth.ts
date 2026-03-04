/**
 * Auth state management for Baileys sessions.
 * Mirrors TypeScript openclaw src/web/auth-store.ts
 */
import fsSync from "node:fs";
import fs from "node:fs/promises";
import path from "node:path";
import { useMultiFileAuthState } from "@whiskeysockets/baileys";

export const DEFAULT_AUTH_BASE = path.join(
  process.env.HOME ?? "~",
  ".openclaw",
  "credentials",
  "whatsapp",
);

export function resolveAuthDir(accountId: string, override?: string): string {
  if (override) {
    return override.startsWith("~")
      ? path.join(process.env.HOME ?? "~", override.slice(1))
      : override;
  }
  return path.join(DEFAULT_AUTH_BASE, accountId);
}

export function resolveCredsPath(authDir: string): string {
  return path.join(authDir, "creds.json");
}

export function resolveCredsBackupPath(authDir: string): string {
  return path.join(authDir, "creds.json.bak");
}

export function readCredsJsonRaw(filePath: string): string | null {
  try {
    if (!fsSync.existsSync(filePath)) return null;
    const stats = fsSync.statSync(filePath);
    if (!stats.isFile() || stats.size <= 1) return null;
    return fsSync.readFileSync(filePath, "utf-8");
  } catch {
    return null;
  }
}

/**
 * If creds.json is missing or corrupt, restore from .bak if available.
 * Mirrors maybeRestoreCredsFromBackup in auth-store.ts.
 */
export function maybeRestoreCredsFromBackup(authDir: string): void {
  try {
    const credsPath = resolveCredsPath(authDir);
    const backupPath = resolveCredsBackupPath(authDir);
    const raw = readCredsJsonRaw(credsPath);
    if (raw) {
      JSON.parse(raw); // validate
      return;
    }
    const backupRaw = readCredsJsonRaw(backupPath);
    if (!backupRaw) return;
    JSON.parse(backupRaw); // validate backup before restoring
    fsSync.copyFileSync(backupPath, credsPath);
    try { fsSync.chmodSync(credsPath, 0o600); } catch { /* best-effort */ }
  } catch { /* ignore */ }
}

/**
 * Safe credential save: backup existing valid creds before overwriting.
 * Mirrors safeSaveCreds in session.ts.
 */
export async function safeSaveCreds(
  authDir: string,
  saveCreds: () => Promise<void> | void,
): Promise<void> {
  try {
    const credsPath = resolveCredsPath(authDir);
    const backupPath = resolveCredsBackupPath(authDir);
    const raw = readCredsJsonRaw(credsPath);
    if (raw) {
      try {
        JSON.parse(raw);
        fsSync.copyFileSync(credsPath, backupPath);
        try { fsSync.chmodSync(backupPath, 0o600); } catch { /* best-effort */ }
      } catch { /* keep existing backup */ }
    }
  } catch { /* ignore backup failures */ }

  try {
    await Promise.resolve(saveCreds());
    try { fsSync.chmodSync(resolveCredsPath(authDir), 0o600); } catch { /* best-effort */ }
  } catch (err) {
    console.warn(`[bridge] Failed saving WhatsApp creds: ${String(err)}`);
  }
}

export async function loadAuthState(authDir: string) {
  await fs.mkdir(authDir, { recursive: true });
  maybeRestoreCredsFromBackup(authDir);
  return useMultiFileAuthState(authDir);
}

export function hasAuth(authDir: string): boolean {
  try {
    const stats = fsSync.statSync(resolveCredsPath(authDir));
    return stats.isFile() && stats.size > 1;
  } catch {
    return false;
  }
}

export async function clearAuth(authDir: string): Promise<void> {
  try {
    await fs.rm(authDir, { recursive: true, force: true });
  } catch { /* ignore */ }
}

export function readSelfId(authDir: string): { jid: string | null; e164: string | null } {
  try {
    const raw = readCredsJsonRaw(resolveCredsPath(authDir));
    if (!raw) return { jid: null, e164: null };
    const parsed = JSON.parse(raw) as { me?: { id?: string } };
    const jid = parsed?.me?.id ?? null;
    const e164 = jid ? jidToE164(jid) : null;
    return { jid, e164 };
  } catch {
    return { jid: null, e164: null };
  }
}

/** Convert a WhatsApp JID to an E.164 phone number. */
function jidToE164(jid: string): string | null {
  try {
    const bare = jid.split(":")[0]!.split("@")[0]!;
    if (!/^\d+$/.test(bare)) return null;
    return `+${bare}`;
  } catch {
    return null;
  }
}
