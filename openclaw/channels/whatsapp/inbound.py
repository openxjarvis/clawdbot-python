"""WhatsApp inbound message processing pipeline.

Handles the full flow from raw Baileys event to InboundMessage dispatch:
  1. De-duplicate (memory + persistent)
  2. Skip history / fromMe / @status / @broadcast
  3. DM policy check / group gating
  4. Mark read (blue ticks) via bridge
  5. Extract text and media info
  6. Send ack reaction if configured
  7. Debounce consecutive messages
  8. Build and dispatch InboundMessage

Mirrors TypeScript: src/web/inbound/monitor.ts and src/web/auto-reply/monitor/
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from typing import Any, Callable, Awaitable, TYPE_CHECKING

from ...channels.base import InboundMessage

if TYPE_CHECKING:
    from .config import ResolvedWhatsAppAccount
    from .bridge_client import BridgeClient
    from .dedup import WhatsAppDedup

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Message extraction helpers (mirrors src/web/inbound/extract.ts)
# ---------------------------------------------------------------------------

def extract_text(message: dict[str, Any] | None) -> str | None:
    """Extract text content from a Baileys proto message."""
    if not message:
        return None

    # Direct conversation
    if conversation := message.get("conversation"):
        if isinstance(conversation, str) and conversation.strip():
            return conversation.strip()

    # Extended text message
    if ext := message.get("extendedTextMessage"):
        if isinstance(ext, dict):
            if text := ext.get("text"):
                if isinstance(text, str) and text.strip():
                    return text.strip()

    # Image/video/document/audio captions
    for key in ("imageMessage", "videoMessage", "documentMessage", "stickerMessage"):
        if item := message.get(key):
            if isinstance(item, dict):
                if caption := item.get("caption"):
                    if isinstance(caption, str) and caption.strip():
                        return caption.strip()

    # Buttons response
    if btn := message.get("buttonsResponseMessage"):
        if isinstance(btn, dict):
            if text := btn.get("selectedDisplayText") or btn.get("selectedButtonId"):
                if isinstance(text, str) and text.strip():
                    return text.strip()

    # List response
    if lst := message.get("listResponseMessage"):
        if isinstance(lst, dict):
            if text := lst.get("title") or lst.get("singleSelectReply"):
                if isinstance(text, str) and text.strip():
                    return text.strip()

    # Template button reply
    if tmpl := message.get("templateButtonReplyMessage"):
        if isinstance(tmpl, dict):
            if text := tmpl.get("selectedDisplayText") or tmpl.get("selectedId"):
                if isinstance(text, str) and text.strip():
                    return text.strip()

    return None


def extract_media_placeholder(message: dict[str, Any] | None) -> str | None:
    """Extract a text placeholder for media messages that have no caption."""
    if not message:
        return None
    if message.get("imageMessage"):
        return "[image]"
    if message.get("videoMessage"):
        return "[video]"
    if message.get("audioMessage"):
        return "[audio]"
    if message.get("documentMessage"):
        dm = message.get("documentMessage")
        if isinstance(dm, dict) and dm.get("fileName"):
            return f"[document: {dm['fileName']}]"
        return "[document]"
    if message.get("stickerMessage"):
        return "[sticker]"
    if message.get("locationMessage"):
        loc = message.get("locationMessage")
        if isinstance(loc, dict):
            lat = loc.get("degreesLatitude")
            lng = loc.get("degreesLongitude")
            if lat is not None and lng is not None:
                return f"[location: {lat},{lng}]"
        return "[location]"
    if message.get("contactMessage") or message.get("contactsArrayMessage"):
        return "[contact]"
    return None


def extract_mentioned_jids(message: dict[str, Any] | None) -> list[str] | None:
    """Extract mentioned JIDs from contextInfo in various message types."""
    if not message:
        return None

    candidates: list[list[str]] = []
    for key in (
        "extendedTextMessage", "imageMessage", "videoMessage", "documentMessage",
        "audioMessage", "stickerMessage", "buttonsResponseMessage", "listResponseMessage",
    ):
        if item := message.get(key):
            if isinstance(item, dict):
                ctx = item.get("contextInfo")
                if isinstance(ctx, dict):
                    jids = ctx.get("mentionedJid")
                    if isinstance(jids, list):
                        candidates.append(jids)

    # Also check top-level contextInfo
    if ctx := message.get("contextInfo"):
        if isinstance(ctx, dict):
            jids = ctx.get("mentionedJid")
            if isinstance(jids, list):
                candidates.append(jids)

    flattened = list({j for jids in candidates for j in jids if j})
    return flattened if flattened else None


def extract_media_info(message: dict[str, Any] | None) -> dict[str, Any] | None:
    """Extract media metadata from message (type, base64 data, mimetype, fileName).

    The bridge now serializes downloaded media bytes into ``_mediaData`` (base64)
    on the message payload after calling Baileys' downloadMediaMessage().
    Mirrors TS extractMediaInfo() in inbound/extract.ts.
    """
    if not message:
        return None
    for key in ("imageMessage", "videoMessage", "audioMessage", "documentMessage", "stickerMessage"):
        if item := message.get(key):
            if isinstance(item, dict):
                media_b64: str | None = (
                    item.get("_mediaData")       # injected by bridge after download
                    or message.get("_mediaData") # sometimes at top-level
                )
                return {
                    "type": key,
                    "mimetype": item.get("mimetype", "application/octet-stream"),
                    "fileLength": item.get("fileLength"),
                    "fileName": item.get("fileName"),
                    "mediaData": media_b64,  # base64-encoded bytes, None if not downloaded yet
                }
    return None


def extract_reply_context(message: dict[str, Any] | None) -> dict[str, Any] | None:
    """Extract quoted message context."""
    if not message:
        return None
    for key in (
        "extendedTextMessage", "imageMessage", "videoMessage", "documentMessage",
        "audioMessage", "buttonsResponseMessage", "listResponseMessage",
    ):
        if item := message.get(key):
            if isinstance(item, dict):
                ctx = item.get("contextInfo")
                if isinstance(ctx, dict) and ctx.get("quotedMessage"):
                    return {
                        "id": ctx.get("stanzaId"),
                        "participant": ctx.get("participant"),
                        "body": extract_text(ctx.get("quotedMessage")),
                    }
    return None


# ---------------------------------------------------------------------------
# Debouncer
# ---------------------------------------------------------------------------

class _Debouncer:
    """
    Groups rapid messages from the same sender and flushes after debounce_ms.
    Mirrors createInboundDebouncer in auto-reply/inbound-debounce.ts.
    """

    def __init__(self, debounce_ms: int) -> None:
        self._debounce_ms = debounce_ms
        self._pending: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._tasks: dict[str, asyncio.Task] = {}

    async def enqueue(
        self,
        key: str,
        payload: dict[str, Any],
        on_flush: Callable[[list[dict[str, Any]]], Awaitable[None]],
    ) -> None:
        if self._debounce_ms <= 0:
            await on_flush([payload])
            return

        self._pending[key].append(payload)

        # Cancel existing timer
        if key in self._tasks:
            self._tasks[key].cancel()

        async def flush() -> None:
            await asyncio.sleep(self._debounce_ms / 1000.0)
            entries = self._pending.pop(key, [])
            self._tasks.pop(key, None)
            if entries:
                await on_flush(entries)

        self._tasks[key] = asyncio.create_task(flush())


# ---------------------------------------------------------------------------
# Main inbound handler
# ---------------------------------------------------------------------------

DispatchFn = Callable[[InboundMessage], Awaitable[None]]


async def handle_wa_message(
    event: dict[str, Any],
    account: "ResolvedWhatsAppAccount",
    dedup: "WhatsAppDedup",
    bridge_client: "BridgeClient",
    dispatch_fn: DispatchFn,
    debouncer: _Debouncer,
    connected_at_ms: int,
) -> None:
    """
    Process a single inbound message event from the bridge.

    event fields (from bridge):
      type: "message"
      accountId: str
      upsertType: "notify" | "append"
      data: Baileys WAMessage (serialized)
      selfJid: str | None
      selfE164: str | None
      group: bool
    """
    from .accounts import is_group_jid, jid_to_e164
    from .policy import check_dm_policy, apply_group_gating

    upsert_type = event.get("upsertType", "notify")
    msg: dict[str, Any] = event.get("data", {})
    self_jid: str | None = event.get("selfJid")
    self_e164: str | None = event.get("selfE164")
    is_group: bool = event.get("group", False)

    # Extract key fields
    key: dict[str, Any] = msg.get("key", {})
    msg_id: str | None = key.get("id")
    remote_jid: str | None = key.get("remoteJid")
    is_from_me: bool = bool(key.get("fromMe", False))
    participant_jid: str | None = key.get("participant")

    if not remote_jid:
        return

    # Skip status/broadcast
    if remote_jid.endswith("@status") or remote_jid.endswith("@broadcast"):
        return

    # De-duplicate
    if msg_id:
        dedup_key = f"{account.account_id}:{remote_jid}:{msg_id}"
        if not dedup.try_record(dedup_key):
            logger.debug("[whatsapp] Duplicate message %s, skipping", dedup_key)
            return

    message_body = msg.get("message")
    push_name: str | None = msg.get("pushName")
    timestamp_seconds = msg.get("messageTimestamp")
    message_timestamp_ms = int(timestamp_seconds) * 1000 if timestamp_seconds else None

    sender_e164: str | None
    if is_group:
        sender_e164 = jid_to_e164(participant_jid) if participant_jid else None
        from_id = remote_jid
    else:
        sender_e164 = jid_to_e164(remote_jid)
        from_id = sender_e164 or remote_jid

    # --- Access control ---
    if is_group:
        mentioned_jids = extract_mentioned_jids(message_body)
        reply_ctx = extract_reply_context(message_body)
        is_reply_to_bot = (
            reply_ctx is not None and
            reply_ctx.get("participant") is not None and
            self_jid is not None and
            reply_ctx["participant"].split("@")[0] == self_jid.split("@")[0].split(":")[0]
        )
        if not apply_group_gating(
            account,
            remote_jid,
            sender_e164,
            mentioned_jids,
            self_jid,
            is_reply_to_bot,
        ):
            return
    else:
        result = check_dm_policy(
            account,
            sender_e164,
            is_from_me,
            message_timestamp_ms,
            connected_at_ms,
        )
        if not result.allowed:
            if result.send_pairing_reply:
                # Send pairing code to unknown DM sender (mirrors TS sendPairingReply())
                logger.info("[whatsapp] Pairing request from %s — sending pairing code", sender_e164)
                asyncio.create_task(
                    _send_wa_pairing_reply(bridge_client, account, remote_jid, sender_e164)
                )
            return

    # --- Mark read (blue ticks) ---
    if msg_id and account.send_read_receipts and not (
        is_group is False and  # self-chat: don't send read receipts
        account.self_chat_mode
    ):
        try:
            await bridge_client.mark_read(
                account.account_id,
                [{"remoteJid": remote_jid, "id": msg_id, "participant": participant_jid, "fromMe": False}],
            )
        except Exception as e:
            logger.debug("[whatsapp] Mark read failed: %s", e)

    # --- Skip history catch-up (after marking read) ---
    if upsert_type == "append":
        return

    # --- Extract text and media ---
    body = extract_text(message_body)
    if not body:
        body = extract_media_placeholder(message_body)
    if not body:
        return

    mentioned_jids_list = extract_mentioned_jids(message_body) or []
    reply_context = extract_reply_context(message_body)
    media_info = extract_media_info(message_body)

    # --- Ack reaction ---
    if msg_id and account.ack_reaction.emoji:
        await _maybe_send_ack_reaction(
            account, bridge_client, remote_jid, msg_id, is_group,
            bool(mentioned_jids_list and self_jid and
                 any(j.split("@")[0] == self_jid.split("@")[0].split(":")[0] for j in mentioned_jids_list))
        )

    # --- Build InboundMessage factory ---
    def build_inbound(entries: list[dict[str, Any]]) -> InboundMessage:
        last = entries[-1]
        if len(entries) == 1:
            combined_body = last["body"]
        else:
            combined_body = "\n".join(e["body"] for e in entries if e.get("body"))

        return InboundMessage(
            id=last.get("msgId"),
            channel_id="whatsapp",
            account_id=account.account_id,
            conversation_id=remote_jid,
            sender_id=sender_e164 or participant_jid or remote_jid,
            sender_name=push_name,
            body=combined_body,
            chat_type="group" if is_group else "direct",
            timestamp=message_timestamp_ms,
            reply_to_id=reply_context.get("id") if reply_context else None,
            metadata={
                "remote_jid": remote_jid,
                "self_jid": self_jid,
                "self_e164": self_e164,
                "sender_jid": participant_jid if is_group else remote_jid,
                "push_name": push_name,
                "mentioned_jids": mentioned_jids_list,
                "media_info": media_info,
                "reply_context": reply_context,
            },
        )

    # --- Debounce ---
    debounce_key = (
        f"{account.account_id}:{remote_jid}:{sender_e164 or participant_jid or 'anon'}"
    )
    entry = {
        "body": body,
        "msgId": msg_id,
        "senderE164": sender_e164,
        "mentionedJids": mentioned_jids_list,
    }

    async def on_flush(entries: list[dict[str, Any]]) -> None:
        inbound = build_inbound(entries)
        try:
            await dispatch_fn(inbound)
        except Exception as e:
            logger.error("[whatsapp] Error dispatching inbound message: %s", e, exc_info=True)

    await debouncer.enqueue(debounce_key, entry, on_flush)


async def _send_wa_pairing_reply(
    bridge_client: "BridgeClient",
    account: "ResolvedWhatsAppAccount",
    remote_jid: str,
    sender_e164: str | None,
) -> None:
    """Send a pairing code message to an unknown DM sender.

    Mirrors TS sendPairingReply() in inbound/monitor.ts.
    """
    try:
        from openclaw.pairing.approval import upsert_pairing_request  # type: ignore
        from openclaw.pairing.messages import build_pairing_message  # type: ignore

        ident = sender_e164 or remote_jid.split("@")[0]
        pairing_info = upsert_pairing_request(account.account_id, ident)
        msg = build_pairing_message(pairing_info)
        await bridge_client.send_message(account.account_id, remote_jid, msg)
    except ImportError:
        # Pairing module not available; send a generic "not authorized" message
        try:
            await bridge_client.send_message(
                account.account_id, remote_jid,
                "⚠️ You are not authorized to use this bot. Contact the bot owner for access."
            )
        except Exception as inner_err:
            logger.debug("[whatsapp] Failed to send not-authorized message: %s", inner_err)
    except Exception as e:
        logger.debug("[whatsapp] Failed to send pairing reply to %s: %s", remote_jid, e)


async def _maybe_send_ack_reaction(
    account: "ResolvedWhatsAppAccount",
    bridge_client: "BridgeClient",
    remote_jid: str,
    msg_id: str,
    is_group: bool,
    is_mentioned: bool,
) -> None:
    """Send ack reaction if configured for this chat type."""
    cfg = account.ack_reaction
    if not cfg.emoji:
        return

    should_react = False
    if not is_group and cfg.direct:
        should_react = True
    elif is_group:
        if cfg.group == "always":
            should_react = True
        elif cfg.group == "mentions" and is_mentioned:
            should_react = True

    if not should_react:
        return

    try:
        await bridge_client.send_reaction(
            account.account_id,
            remote_jid,
            msg_id,
            cfg.emoji,
        )
    except Exception as e:
        logger.debug("[whatsapp] Ack reaction failed: %s", e)
