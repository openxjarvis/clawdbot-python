"""Outbound message delivery infrastructure.

Handles delivering reply payloads to channels with media support.
Mirrors TypeScript: openclaw/src/infra/outbound/deliver.ts
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


async def deliver_outbound_payloads(
    *,
    cfg: Any,
    channel: str,
    to: str,
    account_id: str | None = None,
    payloads: list[dict[str, Any]],
    reply_to_id: str | None = None,
    thread_id: str | int | None = None,
    agent_id: str | None = None,
    abort_signal: Any = None,
    mirror: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Deliver one or more reply payloads to a channel.
    
    Mirrors TS deliverOutboundPayloads() — sends text + media to channels.
    
    Args:
        cfg: OpenClaw config
        channel: Target channel ID (telegram, feishu, slack, etc.)
        to: Target chat/user ID
        account_id: Provider account ID
        payloads: List of normalized reply payloads (each with text/mediaUrl/mediaUrls)
        reply_to_id: Message ID to reply to
        thread_id: Thread/topic ID
        agent_id: Agent ID for session context
        abort_signal: Abort signal for cooperative cancellation
        mirror: Mirror config for session transcript
    
    Returns:
        List of delivery results (each with messageId, ok, error)
    """
    from openclaw.channels.plugins import get_channel_plugin
    
    results = []
    
    try:
        # Get channel plugin
        channel_plugin = get_channel_plugin(channel)
        if not channel_plugin:
            error_msg = f"Channel not found: {channel}"
            logger.warning(f"[outbound] {error_msg}")
            return [{"ok": False, "error": error_msg}]
        
        # Check capabilities
        if not channel_plugin.capabilities.supports_media:
            logger.debug(f"[outbound] Channel {channel} doesn't support media")
        
        # Process each payload
        for payload in payloads:
            text = payload.get("text", "")
            media_url = payload.get("mediaUrl")
            media_urls = payload.get("mediaUrls", [])
            
            # Build media URLs list
            if media_urls and isinstance(media_urls, list):
                media_urls = [url for url in media_urls if url]
            elif media_url:
                media_urls = [media_url]
            else:
                media_urls = []
            
            # Check abort signal
            if abort_signal and hasattr(abort_signal, "is_set") and abort_signal.is_set():
                logger.debug("[outbound] Aborted during delivery")
                results.append({"ok": False, "error": "Aborted"})
                break
            
            # Send text message
            if text and text.strip():
                try:
                    msg_id = await channel_plugin.send_message(
                        target=to,
                        text=text,
                        account_id=account_id,
                        reply_to=reply_to_id,
                        thread_id=thread_id,
                    )
                    results.append({
                        "ok": True,
                        "messageId": msg_id,
                        "channel": channel,
                    })
                except Exception as e:
                    logger.warning(f"[outbound] Failed to send text to {channel}: {e}")
                    results.append({
                        "ok": False,
                        "error": str(e),
                    })
            
            # Send media files
            if media_urls and channel_plugin.capabilities.supports_media:
                for media_url in media_urls:
                    try:
                        # Determine media type from file extension
                        ext = Path(media_url.split("?")[0]).suffix.lower()
                        if ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}:
                            media_type = "image"
                        elif ext in {".mp4", ".mov", ".avi", ".mkv", ".webm"}:
                            media_type = "video"
                        elif ext in {".mp3", ".m4a", ".ogg", ".opus", ".wav", ".aac"}:
                            media_type = "audio"
                        else:
                            media_type = "file"
                        
                        msg_id = await channel_plugin.send_media(
                            target=to,
                            media_url=media_url,
                            media_type=media_type,
                            account_id=account_id,
                            reply_to=reply_to_id,
                        )
                        results.append({
                            "ok": True,
                            "messageId": msg_id,
                            "channel": channel,
                            "mediaUrl": media_url,
                        })
                    except Exception as e:
                        logger.warning(f"[outbound] Failed to send media {media_url} to {channel}: {e}")
                        results.append({
                            "ok": False,
                            "error": str(e),
                            "mediaUrl": media_url,
                        })
            
            # Mirror to session transcript if requested
            if mirror and text:
                try:
                    from openclaw.agents.session import mirror_assistant_message_to_transcript
                    
                    session_key = mirror.get("sessionKey")
                    if session_key:
                        await mirror_assistant_message_to_transcript(
                            session_key=session_key,
                            agent_id=mirror.get("agentId"),
                            text=text,
                            media_urls=media_urls,
                        )
                except Exception as e:
                    logger.debug(f"[outbound] Failed to mirror to transcript: {e}")
        
        return results if results else [{"ok": True}]
    
    except Exception as e:
        logger.warning(f"[outbound] Delivery error for {channel}: {e}")
        return [{"ok": False, "error": str(e)}]
