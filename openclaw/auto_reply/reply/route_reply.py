"""Provider-agnostic reply router

Fully aligned with TypeScript openclaw/src/auto-reply/reply/route-reply.ts

Routes replies to the originating channel based on OriginatingChannel/OriginatingTo
instead of using the session's lastChannel. This ensures replies go back to the
provider where the message originated, even when the main session is shared
across multiple providers.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Internal message channel constant (mirrors TS)
INTERNAL_MESSAGE_CHANNEL = "internal"


async def route_reply(
    *,
    payload: dict[str, Any],
    channel: str,
    to: str,
    session_key: str | None = None,
    account_id: str | None = None,
    thread_id: str | int | None = None,
    cfg: Any = None,
    abort_signal: Any = None,
    mirror: bool | None = None,
) -> dict[str, Any]:
    """
    Routes a reply payload to the specified channel.
    
    Fully aligned with TS routeReply() from route-reply.ts lines 57-151
    
    This function provides a unified interface for sending messages to any
    supported provider. It's used by the followup queue to route replies
    back to the originating channel when OriginatingChannel/OriginatingTo
    are set.
    
    Args:
        payload: The reply payload to send
        channel: The originating channel type (telegram, slack, etc)
        to: The destination chat/channel/user ID
        session_key: Session key for deriving agent identity defaults
        account_id: Provider account id (multi-account)
        thread_id: Thread id for replies (Telegram topic id or Matrix thread event id)
        cfg: Config for provider-specific settings
        abort_signal: Optional abort signal for cooperative cancellation
        mirror: Mirror reply into session transcript (default: True when session_key is set)
    
    Returns:
        Dict with:
        - ok: bool - Whether the reply was sent successfully
        - messageId: str (optional) - Message ID from the provider
        - error: str (optional) - Error message if send failed
    """
    # Normalize channel
    from openclaw.utils.message_channel import normalize_message_channel
    
    normalized_channel = normalize_message_channel(channel)
    
    # Resolve agent ID
    resolved_agent_id = None
    if session_key:
        try:
            from openclaw.agents.agent_scope import resolve_session_agent_id
            resolved_agent_id = resolve_session_agent_id(
                session_key=session_key,
                config=cfg,
            )
        except Exception as e:
            logger.debug(f"Failed to resolve agent ID: {e}")
    
    # Resolve response prefix
    response_prefix = None
    if cfg and hasattr(cfg, "messages"):
        messages_cfg = cfg.messages
        if hasattr(messages_cfg, "responsePrefix"):
            if messages_cfg.responsePrefix != "auto":
                response_prefix = messages_cfg.responsePrefix
    
    # Normalize payload
    from openclaw.auto_reply.reply.normalize_reply import normalize_reply_payload
    
    normalized = normalize_reply_payload(
        payload,
        response_prefix=response_prefix,
    )
    
    if not normalized:
        return {"ok": True}
    
    # Extract fields
    text = normalized.get("text", "")
    media_url = normalized.get("mediaUrl")
    media_urls = normalized.get("mediaUrls", [])
    
    # Build media URLs list
    if media_urls and isinstance(media_urls, list):
        media_urls = [url for url in media_urls if url]
    elif media_url:
        media_urls = [media_url]
    else:
        media_urls = []
    
    reply_to_id = normalized.get("replyToId")
    
    # Skip empty replies
    if not text.strip() and not media_urls:
        return {"ok": True}
    
    # Check for internal channel
    if channel == INTERNAL_MESSAGE_CHANNEL:
        return {
            "ok": False,
            "error": "Webchat routing not supported for queued replies",
        }
    
    # Normalize channel ID
    try:
        from openclaw.channels.plugins import normalize_channel_id
        channel_id = normalize_channel_id(channel)
    except Exception:
        channel_id = None
    
    if not channel_id:
        return {"ok": False, "error": f"Unknown channel: {channel}"}
    
    # Check abort signal
    if abort_signal and hasattr(abort_signal, "is_set") and abort_signal.is_set():
        return {"ok": False, "error": "Reply routing aborted"}
    
    # Resolve reply_to_id and thread_id (Slack special handling)
    resolved_reply_to_id = reply_to_id
    resolved_thread_id = thread_id
    
    if channel_id == "slack" and thread_id is not None and thread_id != "":
        resolved_reply_to_id = resolved_reply_to_id or str(thread_id)
        resolved_thread_id = None
    
    try:
        # Deliver outbound payloads
        from openclaw.infra.outbound.deliver import deliver_outbound_payloads
        
        mirror_config = None
        if (mirror is None or mirror) and session_key:
            mirror_config = {
                "sessionKey": session_key,
                "agentId": resolved_agent_id,
                "text": text,
                "mediaUrls": media_urls,
            }
        
        results = await deliver_outbound_payloads(
            cfg=cfg,
            channel=channel_id,
            to=to,
            account_id=account_id,
            payloads=[normalized],
            reply_to_id=resolved_reply_to_id,
            thread_id=resolved_thread_id,
            agent_id=resolved_agent_id,
            abort_signal=abort_signal,
            mirror=mirror_config,
        )
        
        # Get last message ID
        message_id = None
        if results and isinstance(results, list) and results:
            last = results[-1]
            if isinstance(last, dict):
                message_id = last.get("messageId")
        
        return {"ok": True, "messageId": message_id}
    
    except Exception as err:
        message = str(err) if not isinstance(err, Exception) else err.args[0] if err.args else str(err)
        return {
            "ok": False,
            "error": f"Failed to route reply to {channel}: {message}",
        }


def is_routable_channel(channel: str | None) -> bool:
    """
    Checks if a channel type is routable via route_reply.
    
    Mirrors TS isRoutableChannel() from route-reply.ts lines 159-166
    
    Some channels (webchat/internal) require special handling and cannot be routed
    through this generic interface.
    
    Args:
        channel: Channel type to check
    
    Returns:
        True if channel can be routed via route_reply
    """
    if not channel or channel == INTERNAL_MESSAGE_CHANNEL:
        return False
    
    try:
        from openclaw.channels.plugins import normalize_channel_id
        return normalize_channel_id(channel) is not None
    except Exception:
        return False
