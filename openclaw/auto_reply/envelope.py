"""Inbound message envelope formatting helpers.

Mirrors TypeScript src/auto-reply/envelope.ts — formatInboundEnvelope and related.

The envelope wraps a message body with a bracketed header containing channel,
sender, and optional timestamp information so the LLM has full context about
each history entry.

Example output: ``[WhatsApp SenderName: body text here]``
"""
from __future__ import annotations

import datetime
import hashlib
from dataclasses import dataclass
from typing import Any


@dataclass
class InboundEnvelope:
    """Inbound message envelope for deduplication and routing.
    
    Mirrors TS InboundEnvelope pattern (used in deduplication and dispatch).
    
    Attributes:
        message_id: Unique message identifier
        channel: Channel name
        from_: Sender identifier
        body: Message body
        timestamp: Message timestamp
        message_hash: Computed hash for deduplication
    """
    message_id: str
    channel: str
    from_: str
    body: str
    timestamp: int | float | None = None
    message_hash: str | None = None
    
    def __post_init__(self):
        """Compute message hash if not provided."""
        if self.message_hash is None:
            # Compute stable hash from message_id + channel + body
            hash_input = f"{self.message_id}:{self.channel}:{self.body}"
            self.message_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]


@dataclass
class EnvelopeFormatOptions:
    """Envelope formatting options for message context headers.
    
    Mirrors TS EnvelopeFormatOptions from envelope.ts.
    
    Attributes:
        timezone: "local" (default), "utc", "user", or an explicit IANA timezone string
        include_timestamp: Include absolute timestamps in envelope (default: True)
        include_elapsed: Include elapsed time suffix when previousTimestamp provided (default: True)
        user_timezone: Optional user timezone used when timezone="user"
    """
    timezone: str = "local"
    include_timestamp: bool = True
    include_elapsed: bool = True
    user_timezone: str | None = None


def resolve_envelope_format_options(cfg: dict[str, Any] | None) -> EnvelopeFormatOptions:
    """Resolve envelope format options from config.
    
    Mirrors TS resolveEnvelopeFormatOptions(cfg) from envelope.ts lines 65-73.
    Reads cfg.agents.defaults.envelopeTimezone, envelopeTimestamp, envelopeElapsed, userTimezone.
    """
    if not cfg or not isinstance(cfg, dict):
        return EnvelopeFormatOptions()
    
    agents = cfg.get("agents") or {}
    defaults = agents.get("defaults") if isinstance(agents, dict) else {}
    if not isinstance(defaults, dict):
        return EnvelopeFormatOptions()
    
    timezone = defaults.get("envelopeTimezone") or "local"
    include_timestamp = defaults.get("envelopeTimestamp") != "off"
    include_elapsed = defaults.get("envelopeElapsed") != "off"
    user_timezone = defaults.get("userTimezone")
    
    return EnvelopeFormatOptions(
        timezone=str(timezone),
        include_timestamp=include_timestamp,
        include_elapsed=include_elapsed,
        user_timezone=str(user_timezone) if user_timezone else None,
    )


def _format_time_ago(elapsed_ms: float) -> str | None:
    """Format elapsed milliseconds as a human-readable relative time string.
    
    Mirrors TS formatTimeAgo from infra/format-time/format-relative.ts.
    Returns None for invalid inputs.
    """
    if not isinstance(elapsed_ms, (int, float)) or elapsed_ms < 0:
        return None
    
    seconds = elapsed_ms / 1000.0
    if seconds < 60:
        return f"{int(seconds)}s"
    
    minutes = seconds / 60.0
    if minutes < 60:
        return f"{int(minutes)}min"
    
    hours = minutes / 60.0
    if hours < 24:
        return f"{int(hours)}h"
    
    days = hours / 24.0
    return f"{int(days)}d"


def _sanitize_header_part(value: str) -> str:
    """Remove characters that would break the bracketed header.

    Mirrors TS ``sanitizeEnvelopeHeaderPart``.
    """
    return (
        value.replace("\r\n", " ")
        .replace("\r", " ")
        .replace("\n", " ")
        .replace("[", "(")
        .replace("]", ")")
        .replace("  ", " ")
        .strip()
    )


def _format_timestamp_part(
    ts: int | float | None,
    envelope: EnvelopeFormatOptions | None = None,
) -> str | None:
    """Format a Unix-millisecond timestamp as a short human-readable string.

    Returns None when the timestamp is absent or invalid.
    Mirrors TS formatTimestamp from envelope.ts lines 105-150.
    
    Args:
        ts: Unix timestamp (seconds or milliseconds)
        envelope: Envelope format options (timezone, includeTimestamp)
    """
    if ts is None:
        return None
    
    options = envelope or EnvelopeFormatOptions()
    if not options.include_timestamp:
        return None
    
    try:
        ms = float(ts)
        if ms <= 0:
            return None
        # Heuristic: values >1e10 are milliseconds, otherwise seconds
        if ms > 1e10:
            ms = ms / 1000.0
        
        # For now, always use UTC (timezone-aware formatting requires additional logic)
        # TS has complex resolveEnvelopeTimezone + formatZonedTimestamp logic
        dt = datetime.datetime.fromtimestamp(ms, tz=datetime.timezone.utc)
        weekday = dt.strftime("%a")
        formatted = dt.strftime("%Y-%m-%d %H:%M UTC")
        return f"{weekday} {formatted}"
    except Exception:
        return None


def format_inbound_envelope(
    *,
    channel: str,
    from_: str = "",
    body: str,
    timestamp: int | float | None = None,
    chat_type: str | None = None,
    sender_label: str | None = None,
    from_me: bool = False,
    previous_timestamp: int | float | None = None,
    envelope: EnvelopeFormatOptions | None = None,
) -> str:
    """Format an inbound message with a standardised envelope header.

    Mirrors TS ``formatInboundEnvelope`` from envelope.ts lines 190-220.

    For group messages with a ``sender_label``, the body is prefixed as
    ``{senderLabel}: {body}``.  For self-chat DMs (``from_me=True``), the body
    is prefixed with ``(self): ``.

    The resulting string has the form::

        [WhatsApp SenderName: body text]

    or, when a timestamp is available::

        [WhatsApp SenderName Thu 2025-01-15 10:00 UTC: body text]
        
    Args:
        channel: Channel name (e.g., "WhatsApp")
        from_: Sender identifier
        body: Message body text
        timestamp: Message timestamp (Unix seconds or milliseconds)
        chat_type: "group" or "dm"/"direct"
        sender_label: Display name for group message sender
        from_me: Whether this is a self-sent message
        previous_timestamp: Previous message timestamp for elapsed-time suffix
        envelope: Envelope format options (timezone, includeElapsed, etc.)
    """
    is_direct = not chat_type or chat_type.lower() in ("dm", "direct")

    if not is_direct and sender_label and sender_label.strip():
        resolved_sender = _sanitize_header_part(sender_label.strip())
        formatted_body = f"{resolved_sender}: {body}"
    elif is_direct and from_me:
        formatted_body = f"(self): {body}"
    else:
        formatted_body = body

    return _format_agent_envelope(
        channel=channel,
        from_=from_,
        timestamp=timestamp,
        previous_timestamp=previous_timestamp,
        envelope=envelope,
        body=formatted_body,
    )


def _format_agent_envelope(
    *,
    channel: str,
    from_: str = "",
    body: str,
    timestamp: int | float | None = None,
    previous_timestamp: int | float | None = None,
    envelope: EnvelopeFormatOptions | None = None,
) -> str:
    """Build the bracketed-header envelope string.

    Mirrors TS ``formatAgentEnvelope`` from envelope.ts lines 152-188.
    
    Args:
        channel: Channel name
        from_: Sender identifier
        body: Message body text
        timestamp: Message timestamp
        previous_timestamp: Previous message timestamp for elapsed-time suffix
        envelope: Envelope format options
    """
    options = envelope or EnvelopeFormatOptions()
    channel_clean = _sanitize_header_part(channel.strip() or "Channel")
    parts: list[str] = [channel_clean]
    
    # Compute elapsed time suffix if previous_timestamp is provided
    elapsed: str | None = None
    if options.include_elapsed and timestamp and previous_timestamp:
        try:
            current_ms = float(timestamp) if timestamp < 1e10 else float(timestamp)
            if timestamp < 1e10:
                current_ms = current_ms * 1000.0
            prev_ms = float(previous_timestamp) if previous_timestamp < 1e10 else float(previous_timestamp)
            if previous_timestamp < 1e10:
                prev_ms = prev_ms * 1000.0
            elapsed_ms = current_ms - prev_ms
            if elapsed_ms >= 0:
                elapsed = _format_time_ago(elapsed_ms)
        except Exception:
            pass

    if from_ and from_.strip():
        from_clean = _sanitize_header_part(from_.strip())
        if elapsed:
            parts.append(f"{from_clean} +{elapsed}")
        else:
            parts.append(from_clean)
    elif elapsed:
        parts.append(f"+{elapsed}")

    ts_str = _format_timestamp_part(timestamp, options)
    if ts_str:
        parts.append(ts_str)

    header = "[" + " ".join(parts) + "]"
    return f"{header} {body}"


def build_inbound_line(
    *,
    msg: dict[str, Any],
    agent_id: str = "",
    cfg: dict[str, Any] | None = None,
    previous_timestamp: int | float | None = None,
    envelope: EnvelopeFormatOptions | None = None,
) -> str:
    """Format the current inbound message as an agent-readable envelope line.

    Mirrors TS ``buildInboundLine`` from ``web/auto-reply/monitor/message-line.ts``.

    Applies a ``messagePrefix`` (if configured) and wraps the body with
    ``format_inbound_envelope``.
    
    Args:
        msg: Message dictionary
        agent_id: Agent ID for resolving message prefix
        cfg: Configuration dictionary
        previous_timestamp: Previous message timestamp for elapsed-time suffix
        envelope: Envelope format options
    """
    body: str = msg.get("body") or msg.get("text") or ""
    chat_type: str = msg.get("chatType") or msg.get("chat_type") or "dm"

    # Resolve optional message prefix (e.g., "user")
    message_prefix: str = _resolve_message_prefix(cfg, agent_id)
    prefix_str = f"{message_prefix} " if message_prefix else ""

    # Build reply context annotation (mirrors TS formatReplyContext)
    reply_context = _format_reply_context(msg)
    base_line = f"{prefix_str}{body}"
    if reply_context:
        base_line = f"{base_line}\n\n{reply_context}"

    from_val: str = msg.get("from") or msg.get("from_") or ""
    if chat_type.lower() not in ("group",) and from_val.startswith("whatsapp:"):
        from_val = from_val[len("whatsapp:"):]

    sender_label: str = (
        msg.get("senderName")
        or msg.get("sender_name")
        or msg.get("senderE164")
        or msg.get("sender_e164")
        or ""
    )

    return format_inbound_envelope(
        channel="WhatsApp",
        from_=from_val,
        body=base_line,
        timestamp=msg.get("timestamp"),
        chat_type=chat_type,
        sender_label=sender_label or None,
        from_me=bool(msg.get("fromMe") or msg.get("from_me")),
        previous_timestamp=previous_timestamp,
        envelope=envelope,
    )


def _format_reply_context(msg: dict[str, Any]) -> str | None:
    """Build a reply-to annotation block from message fields.

    Mirrors TS ``formatReplyContext``.
    """
    reply_body = msg.get("replyToBody") or msg.get("reply_to_body") or ""
    if not reply_body:
        return None
    sender = msg.get("replyToSender") or msg.get("reply_to_sender") or "unknown sender"
    reply_id = msg.get("replyToId") or msg.get("reply_to_id") or ""
    id_part = f" id:{reply_id}" if reply_id else ""
    return f"[Replying to {sender}{id_part}]\n{reply_body}\n[/Replying]"


def _resolve_message_prefix(cfg: dict[str, Any] | None, agent_id: str) -> str:
    """Resolve the optional per-agent or global message prefix for inbound lines.

    Simplified port of TS ``resolveMessagePrefix``.
    Returns empty string when no prefix is configured.
    """
    if not cfg or not isinstance(cfg, dict):
        return ""

    # Per-agent config
    agents_cfg = cfg.get("agents") or {}
    if isinstance(agents_cfg, dict) and agent_id:
        agent_cfg = agents_cfg.get(agent_id) or {}
        if isinstance(agent_cfg, dict):
            prefix = agent_cfg.get("messagePrefix")
            if prefix is not None:
                return str(prefix) if prefix else ""

    # WhatsApp channel config
    channels = cfg.get("channels") or {}
    if isinstance(channels, dict):
        wa = channels.get("whatsapp") or {}
        if isinstance(wa, dict):
            prefix = wa.get("messagePrefix")
            if prefix is not None:
                return str(prefix) if prefix else ""

    # Global messages config
    messages = cfg.get("messages") or {}
    if isinstance(messages, dict):
        prefix = messages.get("messagePrefix")
        if prefix is not None:
            return str(prefix) if prefix else ""

    return ""


__all__ = [
    "InboundEnvelope",
    "EnvelopeFormatOptions",
    "resolve_envelope_format_options",
    "format_inbound_envelope",
    "build_inbound_line",
]
