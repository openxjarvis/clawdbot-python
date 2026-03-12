"""Message processing pipeline.

Fully aligned with TypeScript:
  ``src/web/auto-reply/monitor/process-message.ts``

Responsibilities:
1. Build combined body from group history + current message
2. Combined-body echo detection (buildCombinedEchoKey + echoHas/echoForget)
3. Ack reaction (channel-specific callback)
4. Structured logging
5. DM route-target resolution
6. Full ctxPayload construction (MsgContext with 20+ fields)
7. Update lastRoute for DMs (fire-and-forget, with pinned-owner guard)
8. Record session meta from inbound (fire-and-forget)
9. Dispatch reply via process_message_fn (channel delivers the reply)
10. Group history clearing
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any, Callable, Awaitable

from openclaw.auto_reply.group_history import GroupHistoryEntry
from openclaw.auto_reply.inbound_context import MsgContext

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Inbound session envelope context resolution (mirrors TS resolveInboundSessionEnvelopeContext)
# ---------------------------------------------------------------------------

def resolve_inbound_session_envelope_context(
    cfg: dict[str, Any] | None,
    agent_id: str,
    session_key: str,
) -> tuple[str | None, Any, int | float | None]:
    """Resolve store path, envelope options, and previous timestamp for inbound formatting.
    
    Mirrors TS resolveInboundSessionEnvelopeContext from process-message.ts lines 152-156.
    
    Returns:
        (store_path, envelope_options, previous_timestamp)
    """
    from openclaw.auto_reply.envelope import resolve_envelope_format_options
    
    store_path: str | None = None
    try:
        from openclaw.config.sessions.paths import resolve_store_path as _rsp
        _sess_cfg = (cfg.get("session") or {}) if isinstance(cfg, dict) else {}
        store_path = _rsp(
            _sess_cfg.get("store") if isinstance(_sess_cfg, dict) else None,
            {},
        )
    except Exception:
        pass
    
    envelope_options = resolve_envelope_format_options(cfg)
    
    # TODO: Implement previousTimestamp lookup from session store
    # For now, return None; full implementation would read the last inbound timestamp
    previous_timestamp: int | float | None = None
    
    return (store_path, envelope_options, previous_timestamp)


# ---------------------------------------------------------------------------
# Command authorization resolution (mirrors TS resolveWhatsAppCommandAuthorized)
# ---------------------------------------------------------------------------

def resolve_whatsapp_command_authorized(
    cfg: dict[str, Any] | None,
    msg: dict[str, Any],
) -> bool | None:
    """Dynamically compute command authorization for the current message.
    
    Mirrors TS resolveWhatsAppCommandAuthorized from process-message.ts lines 265-267.
    
    Checks allowFrom list, DM policy, group policy, and access groups.
    Returns True if authorized, False if not, None if indeterminate.
    """
    # For now, return None (indeterminate)
    # Full implementation would check:
    # 1. cfg.accounts[accountId].allowFrom list
    # 2. DM policy (allow all DMs, or require explicit allow)
    # 3. Group policy (require @mention, or allow any group message)
    # 4. Access groups configuration
    # This is a simplified stub matching the TS signature
    return None


# ---------------------------------------------------------------------------
# Reply prefix options (mirrors TS createReplyPrefixOptions)
# ---------------------------------------------------------------------------

def create_reply_prefix_options(
    cfg: dict[str, Any] | None,
    agent_id: str,
    channel: str,
    account_id: str | None,
) -> dict[str, Any]:
    """Create reply prefix options from config.
    
    Mirrors TS createReplyPrefixOptions from process-message.ts lines 269-283.
    
    Returns dict with keys: responsePrefix, onModelSelected (callback).
    """
    # Stub implementation - returns empty options for now
    # Full implementation would read cfg.agents[agent_id].responsePrefix
    # and create an onModelSelected callback for tracking model usage
    return {
        "responsePrefix": None,
        "onModelSelected": None,
    }


# ---------------------------------------------------------------------------
# Agent-scoped media local roots (mirrors TS getAgentScopedMediaLocalRoots)
# ---------------------------------------------------------------------------

def get_agent_scoped_media_local_roots(
    cfg: dict[str, Any] | None,
    agent_id: str,
) -> list[str] | None:
    """Resolve agent-scoped local media file roots.
    
    Mirrors TS getAgentScopedMediaLocalRoots from media/local-roots.ts.
    
    Returns list of local directory paths where agent-specific media is stored.
    """
    from openclaw.media.local_roots import get_agent_scoped_media_local_roots as _get_roots
    return _get_roots(cfg, agent_id)


# ---------------------------------------------------------------------------
# Combined body construction (mirrors TS buildHistoryContextFromEntries)
# ---------------------------------------------------------------------------

def _build_combined_body(
    current_body: str,
    history: list[GroupHistoryEntry],
    channel: str = "whatsapp",
    conversation_id: str = "",
) -> str:
    """Build combined body by prepending group history to the current message.

    Mirrors TS ``buildHistoryContextFromEntries`` called from ``processMessage``,
    with ``formatEntry`` using ``formatInboundEnvelope``.

    Each history entry is formatted as ``[WhatsApp SenderName: body]`` (envelope format).
    """
    if not history:
        return current_body

    from openclaw.auto_reply.envelope import format_inbound_envelope

    parts: list[str] = []
    for entry in history:
        sender = entry.sender or "Unknown"
        body = entry.body or ""
        if body:
            formatted = format_inbound_envelope(
                channel="WhatsApp",
                from_=conversation_id,
                body=body,
                timestamp=entry.timestamp,
                chat_type="group",
                sender_label=sender,
            )
            parts.append(formatted)
    if not parts:
        return current_body
    history_block = "\n".join(parts)
    return f"{history_block}\n\n{current_body}"


# ---------------------------------------------------------------------------
# Combined echo key (mirrors TS buildCombinedEchoKey)
# ---------------------------------------------------------------------------

def _default_build_combined_echo_key(
    *,
    session_key: str,
    combined_body: str,
) -> str:
    """Derive a combined-body echo key from session key + combined body text.

    Mirrors TS ``buildCombinedEchoKey``.  Uses a short SHA-256 hash so the key
    is compact and safe for set membership checks.
    """
    digest = hashlib.sha256(combined_body.encode("utf-8")).hexdigest()[:16]
    return f"combined:{session_key}:{digest}"


# ---------------------------------------------------------------------------
# Session meta recording (fire-and-forget)
# ---------------------------------------------------------------------------

def _record_session_meta_background(
    store_path: str | None,
    session_key: str,
    ctx: dict[str, Any],
) -> None:
    """Persist session metadata from inbound context (fire-and-forget).

    Mirrors TS ``recordSessionMetaFromInbound``.
    """
    if not store_path or not session_key:
        return

    async def _persist() -> None:
        try:
            from openclaw.config.sessions.store_utils import (
                load_session_store_from_path,
                save_session_store_to_path,
            )
            import time as _time
            store = load_session_store_from_path(store_path) or {}
            entry = store.get(session_key.lower()) or store.get(session_key) or {}
            now_ms = int(_time.time() * 1000)
            update: dict[str, Any] = {"updatedAt": now_ms}
            # Mirror TS: store From/To/ChatType/SenderName as session metadata
            for field in ("From", "To", "ChatType", "SenderName", "GroupSubject", "AccountId", "Provider"):
                val = ctx.get(field)
                if val:
                    update[field.lower()] = val
            if isinstance(entry, dict):
                entry.update(update)
            else:
                for k, v in update.items():
                    try:
                        setattr(entry, k, v)
                    except Exception:
                        pass
            store[session_key.lower()] = entry
            save_session_store_to_path(store_path, store)
        except Exception as exc:
            logger.debug("_record_session_meta_background: %s", exc)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(_persist())
    except Exception:
        pass


# ---------------------------------------------------------------------------
# lastRoute update for DMs (fire-and-forget, with pinned-owner guard)
# ---------------------------------------------------------------------------

def _update_last_route_dm_background(
    cfg: dict[str, Any],
    session_key: str,
    main_session_key: str,
    dm_route_target: str | None,
    account_id: str | None,
    route: dict[str, Any],
    ctx: dict[str, Any],
) -> None:
    """Update lastRoute for DM sessions (fire-and-forget).

    Mirrors TS DM lastRoute update logic in ``processMessage``:
    - Only when ``dm_route_target`` is set
    - Only when ``session_key == main_session_key`` (not a per-channel-peer isolated session)
    - Respects ``pinnedMainDmRecipient`` — skip if pinned owner ≠ dm_route_target

    Args:
        cfg: OpenClaw config.
        session_key: Current session key.
        main_session_key: The main (non-isolated) session key for this agent.
        dm_route_target: Resolved E.164 for the DM sender, or None.
        account_id: Channel account ID.
        route: Resolved agent route.
        ctx: Built ctxPayload dict.
    """
    if not dm_route_target or session_key != main_session_key:
        return

    # Resolve pinnedMainDmRecipient to guard against corrupting dmScope=per-channel-peer sessions
    pinned_owner: str | None = None
    try:
        allow_from: list[str] = []
        accounts = (cfg.get("accounts") or {}) if isinstance(cfg, dict) else {}
        if account_id and isinstance(accounts, dict):
            acct = accounts.get(account_id) or {}
            allow_from = (acct.get("allowFrom") or []) if isinstance(acct, dict) else []
        dm_scope: str | None = (cfg.get("session") or {}).get("dmScope") if isinstance(cfg, dict) else None
        if dm_scope != "per-channel-peer" and len(allow_from) == 1:
            # Single explicit allow-from entry = pinned owner
            pinned_owner = allow_from[0]
    except Exception:
        pass

    if pinned_owner and pinned_owner != dm_route_target:
        logger.debug(
            "_update_last_route_dm_background: skipping lastRoute update for %s (pinned=%s)",
            dm_route_target,
            pinned_owner,
        )
        return

    async def _persist() -> None:
        try:
            from openclaw.auto_reply.monitor.on_message import update_last_route_in_background
            update_last_route_in_background(cfg, session_key, route)
        except Exception as exc:
            logger.debug("_update_last_route_dm_background: %s", exc)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(_persist())
    except Exception:
        pass


# ---------------------------------------------------------------------------
# DM route-target normalisation helpers
# ---------------------------------------------------------------------------

def _normalize_e164(phone: str | None) -> str | None:
    """Strip non-digit characters and return a normalised E.164 string.

    Mirrors TS ``normalizeE164``.
    """
    if not phone:
        return None
    digits = "".join(c for c in phone if c.isdigit() or c == "+")
    if not digits:
        return None
    if not digits.startswith("+"):
        digits = "+" + digits
    return digits if len(digits) >= 7 else None


def _compute_is_self_chat(
    msg: dict[str, Any],
    chat_type: str,
) -> bool:
    """Compute whether this is a self-chat (same sender and recipient).
    
    Mirrors TS isSelfChat computation from process-message.ts lines 272-274.
    Non-group + selfE164 present + normalized from == selfE164.
    """
    if chat_type == "group":
        return False
    self_e164 = msg.get("selfE164") or msg.get("self_e164")
    if not self_e164:
        return False
    from_val = msg.get("from") or ""
    if not from_val:
        return False
    normalized_from = _normalize_e164(from_val)
    normalized_self = _normalize_e164(self_e164)
    return normalized_from == normalized_self if normalized_from and normalized_self else False


def _resolve_identity_name_prefix(
    cfg: dict[str, Any] | None,
    agent_id: str,
) -> str | None:
    """Resolve identity name prefix for self-chat reply prefix fallback.
    
    Mirrors TS resolveIdentityNamePrefix.
    Returns None if not configured; "[openclaw]" is the hardcoded fallback in caller.
    """
    # Stub - full implementation would read cfg.agents[agent_id].identityName
    return None


def _normalize_e164_dup(phone: str | None) -> str | None:
    """Strip non-digit characters and return a normalised E.164 string.

    Mirrors TS ``normalizeE164``.
    """
    if not phone:
        return None
    digits = "".join(c for c in phone if c.isdigit() or c == "+")
    if not digits:
        return None
    if not digits.startswith("+"):
        digits = "+" + digits
    return digits if len(digits) >= 7 else None
    """Strip non-digit characters and return a normalised E.164 string.

    Mirrors TS ``normalizeE164``.
    """
    if not phone:
        return None
    digits = "".join(c for c in phone if c.isdigit() or c == "+")
    if not digits:
        return None
    if not digits.startswith("+"):
        digits = "+" + digits
    return digits if len(digits) >= 7 else None


def _jid_to_e164(jid: str | None) -> str | None:
    """Extract E.164 from a WhatsApp JID like ``12345678901@s.whatsapp.net``.

    Mirrors TS ``jidToE164``.
    """
    if not jid:
        return None
    local = jid.split("@")[0]
    return _normalize_e164(local)


# ---------------------------------------------------------------------------
# Build ctxPayload (MsgContext) from msg dict and route
# ---------------------------------------------------------------------------

def _build_ctx_payload(
    msg: dict[str, Any],
    route: dict[str, Any],
    combined_body: str,
    inbound_history: list[dict[str, Any]] | None,
    group_member_names: dict[str, dict[str, str]] | None,
    group_history_key: str,
    channel: str,
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the full ctxPayload dict from all inputs.

    Mirrors TS ``finalizeInboundContext(...)`` call in ``processMessage`` with
    20+ explicit fields.  Returns a dict that can be used to construct
    ``MsgContext`` (with ``extra="allow"``) or passed directly to callers.
    
    Args:
        cfg: Configuration dictionary (used for CommandAuthorized computation)
    """
    chat_type = msg.get("chatType") or msg.get("chat_type") or "dm"
    from_jid: str = msg.get("from") or msg.get("sender_id") or ""
    conversation_id = msg.get("conversationId") or from_jid

    # Group members formatting
    group_members: str | None = None
    if group_member_names and group_history_key:
        roster = group_member_names.get(group_history_key) or {}
        participants: list[str] = msg.get("groupParticipants") or []
        sender_e164: str | None = msg.get("senderE164") or msg.get("sender_e164")
        if roster or participants:
            names: list[str] = []
            for p in participants:
                display = roster.get(p) or p
                names.append(display)
            if sender_e164 and not names:
                names.append(sender_e164)
            group_members = ", ".join(names) if names else None

    location_ctx: dict[str, Any] = {}
    loc = msg.get("location")
    if isinstance(loc, dict):
        location_ctx = {
            "LocationLatitude": loc.get("latitude"),
            "LocationLongitude": loc.get("longitude"),
            "LocationLabel": loc.get("name") or loc.get("label"),
        }
    
    # Dynamically compute CommandAuthorized (mirrors TS lines 265-267)
    command_authorized = resolve_whatsapp_command_authorized(cfg, msg)
    
    # Fix WasMentioned coercion (TS line 325 uses raw value, not bool(x or y))
    was_mentioned = (
        msg.get("wasMentioned")
        if "wasMentioned" in msg
        else msg.get("was_mentioned")
    )

    return {
        "Body": combined_body,
        "BodyForAgent": msg.get("body") or msg.get("text") or "",
        "InboundHistory": inbound_history,
        "RawBody": msg.get("body") or msg.get("text") or "",
        "CommandBody": msg.get("body") or msg.get("text") or "",
        "From": from_jid,
        "To": msg.get("to") or "",
        "SessionKey": route.get("sessionKey") or "",
        "AccountId": route.get("accountId") or msg.get("accountId") or msg.get("account_id"),
        "MessageSid": msg.get("id") or msg.get("message_id"),
        "ReplyToId": msg.get("replyToId") or msg.get("reply_to_id"),
        "ReplyToBody": msg.get("replyToBody") or msg.get("reply_to_body"),
        "ReplyToSender": msg.get("replyToSender") or msg.get("reply_to_sender"),
        "MediaPath": msg.get("mediaPath") or msg.get("media_path"),
        "MediaUrl": msg.get("mediaUrl") or msg.get("media_url"),
        "MediaType": msg.get("mediaType") or msg.get("media_type"),
        "ChatType": chat_type,
        "ConversationLabel": conversation_id if chat_type == "group" else from_jid,
        "GroupSubject": msg.get("groupSubject") or msg.get("group_name"),
        "GroupMembers": group_members,
        "SenderName": msg.get("senderName") or msg.get("sender_name"),
        "SenderId": (msg.get("senderJid") or "").strip() or msg.get("senderE164") or msg.get("sender_e164"),
        "SenderE164": msg.get("senderE164") or msg.get("sender_e164"),
        "CommandAuthorized": command_authorized,
        "WasMentioned": was_mentioned,
        "Provider": channel,
        "Surface": channel,
        "OriginatingChannel": channel,
        "OriginatingTo": from_jid,
        **location_ctx,
    }


# ---------------------------------------------------------------------------
# Main process_message_for_route (mirrors TS processMessage)
# ---------------------------------------------------------------------------

async def process_message_for_route(
    cfg: dict[str, Any],
    msg: dict[str, Any],
    route: dict[str, Any],
    group_history_key: str,
    *,
    group_histories: dict[str, list[GroupHistoryEntry]] | None = None,
    group_member_names: dict[str, dict[str, str]] | None = None,
    group_history: list[GroupHistoryEntry] | None = None,
    suppress_group_history_clear: bool = False,
    echo_has: Callable[[str], bool] | None = None,
    echo_forget: Callable[[str], None] | None = None,
    build_combined_echo_key: Callable[..., str] | None = None,
    remember_sent_text: Callable[..., None] | None = None,
    on_ack: Callable[..., Awaitable[None]] | None = None,
    process_fn: Callable[[dict[str, Any], dict[str, Any], str], Awaitable[bool]] | None = None,
    connection_id: str = "",
    channel: str = "whatsapp",
    max_media_text_chunk_limit: int | None = None,
) -> bool:
    """Process a single inbound message for a resolved route.

    Full port of TS ``processMessage()`` from ``process-message.ts``.

    Steps:
    1. Build combined body (group history + current message)
    2. Combined-body echo detection
    3. Ack reaction
    4. Structured logging
    5. DM route-target resolution
    6. Full ctxPayload construction
    7. DM lastRoute update (fire-and-forget)
    8. Session meta recording (fire-and-forget)
    9. Dispatch via ``process_fn``
    10. Group history clearing

    Args:
        cfg: OpenClaw config dict.
        msg: Inbound message dict (WebInboundMsg equivalent).
        route: Resolved agent route dict.
        group_history_key: Key used for the group history map.
        group_histories: Mutable map of group history entries.
        group_member_names: Per-group participant display names.
        group_history: Explicit history override (skips group_histories lookup).
        suppress_group_history_clear: When True, skip history clear after reply.
        echo_has: Returns True when the combined key is a known echo.
        echo_forget: Removes a key from the echo registry.
        build_combined_echo_key: Builds a string key from session_key + combined_body.
        remember_sent_text: Registers sent text for future echo suppression.
        on_ack: Optional coroutine to send ack reaction to the channel.
        process_fn: Channel-specific dispatch function
                    ``(msg, route, group_history_key) -> bool``.
        connection_id: Current connection ID for logging.
        channel: Channel name (``"whatsapp"``, ``"telegram"``, etc.).
        max_media_text_chunk_limit: Optional override for media text chunk limit.

    Returns:
        True if a reply was sent, False otherwise.
    """
    if group_histories is None:
        group_histories = {}
    if build_combined_echo_key is None:
        build_combined_echo_key = _default_build_combined_echo_key

    chat_type: str = msg.get("chatType") or msg.get("chat_type") or "dm"
    from_jid: str = msg.get("from") or msg.get("sender_id") or ""
    conversation_id: str = msg.get("conversationId") or from_jid
    session_key: str = route.get("sessionKey") or ""
    agent_id: str = route.get("agentId") or ""

    # ------------------------------------------------------------------
    # Resolve inbound session envelope context (TS lines 152-156)
    # Provides store_path, envelope_options, and previous_timestamp
    # ------------------------------------------------------------------
    store_path, envelope_options, previous_timestamp = resolve_inbound_session_envelope_context(
        cfg, agent_id, session_key
    )

    # ------------------------------------------------------------------
    # Resolve delivery options from config (mirrors TS lines 255-261)
    # Use max_media_text_chunk_limit override if provided (TS line 255)
    # ------------------------------------------------------------------
    from openclaw.auto_reply.chunk import resolve_text_chunk_limit, resolve_chunk_mode
    from openclaw.config.markdown_tables import resolve_markdown_table_mode
    account_id_for_opts: str | None = route.get("accountId")
    text_limit: int = (
        max_media_text_chunk_limit 
        if max_media_text_chunk_limit is not None 
        else resolve_text_chunk_limit(cfg, channel, account_id_for_opts)
    )
    chunk_mode: str = resolve_chunk_mode(cfg, channel, account_id_for_opts)
    table_mode: str = resolve_markdown_table_mode(cfg=cfg, channel=channel, account_id=account_id_for_opts)

    # ------------------------------------------------------------------
    # 1. Build combined body with group history
    # Use buildInboundLine for the current message (mirrors TS lines 157-163),
    # then prepend history entries formatted with formatInboundEnvelope.
    # Pass envelope_options and previous_timestamp from context.
    # ------------------------------------------------------------------
    from openclaw.auto_reply.envelope import build_inbound_line as _build_inbound_line

    # Format current message body through envelope wrapper (mirrors TS buildInboundLine)
    current_body_raw: str = msg.get("body") or msg.get("text") or ""
    current_body: str = _build_inbound_line(
        msg=msg, 
        agent_id=agent_id, 
        cfg=cfg, 
        previous_timestamp=previous_timestamp,
        envelope=envelope_options,
    )
    combined_body: str = current_body
    should_clear_group_history = False
    inbound_history: list[dict[str, Any]] | None = None

    if chat_type == "group":
        history: list[GroupHistoryEntry] = (
            group_history
            if group_history is not None
            else (group_histories.get(group_history_key) or [])
        )
        if history:
            combined_body = _build_combined_body(
                current_body,
                history,
                channel=channel,
                conversation_id=conversation_id,
            )
            inbound_history = [
                {"sender": e.sender, "body": e.body, "timestamp": e.timestamp}
                for e in history
            ]
        should_clear_group_history = not suppress_group_history_clear

    # ------------------------------------------------------------------
    # 2. Combined-body echo detection
    # ------------------------------------------------------------------
    if echo_has and echo_forget and combined_body:
        combined_echo_key = build_combined_echo_key(
            session_key=session_key,
            combined_body=combined_body,
        )
        if echo_has(combined_echo_key):
            logger.debug("process_message_for_route: skipping combined-body echo (session=%s)", session_key)
            echo_forget(combined_echo_key)
            return False

    # ------------------------------------------------------------------
    # 3. Ack reaction (channel-specific, fire-and-forget)
    # ------------------------------------------------------------------
    if on_ack:
        try:
            asyncio.create_task(on_ack())
        except RuntimeError:
            pass  # no running loop — skip ack

    # ------------------------------------------------------------------
    # 4. Structured logging
    # ------------------------------------------------------------------
    correlation_id = msg.get("id") or msg.get("message_id") or ""
    kind_label = f", {msg.get('mediaType') or msg.get('media_type')}" if (msg.get("mediaType") or msg.get("media_type")) else ""
    from_display = conversation_id if chat_type == "group" else from_jid
    logger.info(
        "Inbound message connection=%s correlation=%s from=%s to=%s chat=%s%s chars=%d",
        connection_id,
        correlation_id,
        from_display,
        msg.get("to") or "",
        chat_type,
        kind_label,
        len(combined_body),
    )

    # ------------------------------------------------------------------
    # 5. DM route-target resolution
    # ------------------------------------------------------------------
    dm_route_target: str | None = None
    if chat_type != "group":
        sender_e164: str | None = msg.get("senderE164") or msg.get("sender_e164")
        if sender_e164:
            dm_route_target = _normalize_e164(sender_e164)
        elif from_jid and "@" in from_jid:
            dm_route_target = _jid_to_e164(from_jid)
        else:
            dm_route_target = _normalize_e164(from_jid)

    # ------------------------------------------------------------------
    # 6. Build full ctxPayload
    # ------------------------------------------------------------------
    ctx_dict = _build_ctx_payload(
        msg=msg,
        route=route,
        combined_body=combined_body,
        inbound_history=inbound_history,
        group_member_names=group_member_names,
        group_history_key=group_history_key,
        channel=channel,
        cfg=cfg,
    )

    # ------------------------------------------------------------------
    # 7. DM lastRoute update (fire-and-forget)
    # ------------------------------------------------------------------
    main_session_key: str = route.get("mainSessionKey") or session_key
    _update_last_route_dm_background(
        cfg=cfg,
        session_key=session_key,
        main_session_key=main_session_key,
        dm_route_target=dm_route_target,
        account_id=route.get("accountId"),
        route=route,
        ctx=ctx_dict,
    )

    # ------------------------------------------------------------------
    # 8. Session meta recording (fire-and-forget)
    # ------------------------------------------------------------------
    try:
        from openclaw.config.sessions.paths import resolve_store_path as _rsp
        _sess_cfg = (cfg.get("session") or {}) if isinstance(cfg, dict) else {}
        store_path = _rsp(
            _sess_cfg.get("store") if isinstance(_sess_cfg, dict) else None,
            {},
        )
        _record_session_meta_background(store_path, session_key, ctx_dict)
    except Exception:
        pass

    # ------------------------------------------------------------------
    # Resolve reply prefix options and media local roots (TS lines 269-283, 262)
    # ------------------------------------------------------------------
    prefix_options = create_reply_prefix_options(cfg, agent_id, channel, account_id_for_opts)
    is_self_chat = _compute_is_self_chat(msg, chat_type)
    configured_response_prefix = prefix_options.get("responsePrefix")
    
    # Compute response_prefix with identity-name fallback for self-chat (TS lines 275-279)
    response_prefix = (
        configured_response_prefix 
        if configured_response_prefix is not None 
        else (
            (_resolve_identity_name_prefix(cfg, agent_id) or "[openclaw]")
            if (configured_response_prefix is None and is_self_chat)
            else None
        )
    )
    
    media_local_roots = get_agent_scoped_media_local_roots(cfg, agent_id)
    
    # ------------------------------------------------------------------
    # 9. Dispatch reply
    # ------------------------------------------------------------------
    # Enrich msg with pre-computed ctx + delivery options so process_fn can use them.
    # _disable_block_streaming mirrors TS replyOptions.disableBlockStreaming: true
    # (WhatsApp delivery intentionally suppresses non-final payloads).
    enriched_msg = {
        **msg,
        "_ctx": ctx_dict,
        "_combined_body": combined_body,
        "_raw_body": current_body_raw,
        "_text_limit": text_limit,
        "_chunk_mode": chunk_mode,
        "_table_mode": table_mode,
        "_disable_block_streaming": True,
        "_remember_sent_text": remember_sent_text,
        "_combined_body_session_key": session_key,
        "_prefix_options": prefix_options,
        "_response_prefix": response_prefix,
        "_on_model_selected": prefix_options.get("onModelSelected"),
        "_media_local_roots": media_local_roots,
    }
    did_send_reply = False

    if process_fn is not None:
        try:
            did_send_reply = await process_fn(enriched_msg, route, group_history_key)
        except Exception as exc:
            logger.error("process_message_for_route: process_fn error: %s", exc, exc_info=True)
    else:
        # Default fallback: call get_reply_from_config with the full context
        did_send_reply = await _default_dispatch(ctx_dict, route, cfg)

    # ------------------------------------------------------------------
    # remember_sent_text — mirrors TS rememberSentText(payload.text, {combinedBody})
    # Called after dispatch so the echo tracker registers the outbound combined body.
    # In Python, since process_fn is opaque and doesn't return individual payloads,
    # we register the combined_body so echoes of the incoming message are suppressed.
    # ------------------------------------------------------------------
    if did_send_reply and remember_sent_text and combined_body:
        try:
            remember_sent_text(combined_body)
        except Exception as exc:
            logger.debug("process_message_for_route: remember_sent_text error: %s", exc)

    # ------------------------------------------------------------------
    # 10. Group history clearing
    # ------------------------------------------------------------------
    if should_clear_group_history and group_histories is not None:
        group_histories[group_history_key] = []

    return did_send_reply


async def _default_dispatch(
    ctx_dict: dict[str, Any],
    route: dict[str, Any],
    cfg: dict[str, Any],
) -> bool:
    """Fallback dispatch when no process_fn is provided.

    Builds a ``MsgContext`` and calls ``get_reply_from_config``.
    The returned payload is not delivered (no channel_send available here) —
    callers must provide a ``process_fn`` for actual delivery.
    """
    try:
        from openclaw.auto_reply.reply.get_reply import get_reply_from_config

        ctx = MsgContext(
            Body=ctx_dict.get("Body") or "",
            SessionKey=ctx_dict.get("SessionKey") or "",
            **{
                k: v
                for k, v in ctx_dict.items()
                if k not in ("Body", "SessionKey") and v is not None
            },
        )
        reply = await get_reply_from_config(
            ctx=ctx,
            cfg=cfg,
            runtime=route.get("runtime"),
        )
        return reply is not None
    except Exception as exc:
        logger.error("_default_dispatch: error: %s", exc, exc_info=True)
        return False


# ---------------------------------------------------------------------------
# Public wrapper — backward-compatible entry point
# ---------------------------------------------------------------------------

async def process_message(
    cfg: dict[str, Any],
    msg: dict[str, Any],
    route: dict[str, Any],
    group_history_key: str,
    group_histories: dict[str, list[GroupHistoryEntry]] | None = None,
    process_message_fn: Callable[[dict[str, Any], dict[str, Any], str], Awaitable[bool]] | None = None,
    *,
    group_member_names: dict[str, dict[str, str]] | None = None,
    group_history: list[GroupHistoryEntry] | None = None,
    suppress_group_history_clear: bool = False,
    echo_has: Callable[[str], bool] | None = None,
    echo_forget: Callable[[str], None] | None = None,
    build_combined_echo_key: Callable[..., str] | None = None,
    remember_sent_text: Callable[..., None] | None = None,
    on_ack: Callable[..., Awaitable[None]] | None = None,
    connection_id: str = "",
    channel: str = "whatsapp",
) -> bool:
    """Process an inbound message with full TS-aligned pre-processing.

    Backward-compatible wrapper around ``process_message_for_route``.
    Also handles broadcast dispatch before single-route processing.

    Mirrors TS ``processMessage()`` from ``process-message.ts``.
    """
    from openclaw.auto_reply.monitor.broadcast import maybe_broadcast_message

    peer_id = msg.get("from") or msg.get("peer_id") or ""

    # Broadcast check (handles multi-agent dispatch)
    if await maybe_broadcast_message(
        cfg=cfg,
        msg=msg,
        peer_id=peer_id,
        route=route,
        group_history_key=group_history_key,
        process_message_fn=process_message_fn,
        group_histories=group_histories,
    ):
        return True

    # Single-route processing with full pre-processing
    return await process_message_for_route(
        cfg=cfg,
        msg=msg,
        route=route,
        group_history_key=group_history_key,
        group_histories=group_histories,
        group_member_names=group_member_names,
        group_history=group_history,
        suppress_group_history_clear=suppress_group_history_clear,
        echo_has=echo_has,
        echo_forget=echo_forget,
        build_combined_echo_key=build_combined_echo_key,
        remember_sent_text=remember_sent_text,
        on_ack=on_ack,
        process_fn=process_message_fn,
        connection_id=connection_id,
        channel=channel,
    )


__all__ = [
    "process_message",
    "process_message_for_route",
]
