"""Reply payload filters and reply threading utilities.

Mirrors TypeScript src/auto-reply/reply/reply-payloads.ts

Provides:
  - filter_messaging_tool_duplicates(): strips text payloads already sent via messaging tool
  - filter_messaging_tool_media_duplicates(): strips media already sent via tool
  - should_suppress_messaging_tool_replies(): suppress entire reply if tool sent to same destination
  - apply_reply_threading(): 3-step pipeline for reply-to threading on followup payloads
"""
from __future__ import annotations

import re
import logging
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from openclaw.auto_reply.reply.get_reply import ReplyPayload

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Text normalization for dedup — mirrors TS normalizeTextForComparison()
# ---------------------------------------------------------------------------

MIN_DUPLICATE_TEXT_LENGTH = 10


def _normalize_text_for_comparison(text: str) -> str:
    """Normalize text for duplicate comparison.

    Mirrors TS normalizeTextForComparison().
    - Trim whitespace
    - Lowercase
    - Strip emoji (basic range)
    - Collapse spaces
    """
    normalized = text.strip().lower()
    # Strip common emoji ranges (simplified; TS uses Unicode property escapes)
    normalized = re.sub(
        r"[\U0001F300-\U0001FFFF\U00002600-\U000027FF\U0000FE00-\U0000FEFF]",
        "",
        normalized,
    )
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _is_messaging_tool_duplicate(text: str, sent_texts: list[str]) -> bool:
    """Return True when text substantially overlaps with an already-sent message.

    Mirrors TS isMessagingToolDuplicate().
    """
    if not sent_texts:
        return False
    normalized = _normalize_text_for_comparison(text)
    if not normalized or len(normalized) < MIN_DUPLICATE_TEXT_LENGTH:
        return False
    for sent in sent_texts:
        normalized_sent = _normalize_text_for_comparison(sent)
        if not normalized_sent or len(normalized_sent) < MIN_DUPLICATE_TEXT_LENGTH:
            continue
        if normalized in normalized_sent or normalized_sent in normalized:
            return True
    return False


# ---------------------------------------------------------------------------
# Gap 3 — filter_messaging_tool_duplicates
# ---------------------------------------------------------------------------

def filter_messaging_tool_duplicates(
    payloads: list[Any],
    sent_texts: list[str],
) -> list[Any]:
    """Remove payloads whose text was already delivered via a messaging tool.

    Mirrors TS filterMessagingToolDuplicates().
    """
    if not sent_texts:
        return payloads
    return [
        p for p in payloads
        if not _is_messaging_tool_duplicate(p.text or "", sent_texts)
    ]


def _normalize_media_for_dedupe(value: str) -> str:
    """Normalize a media URL/path for dedup comparison.

    Mirrors TS normalizeMediaForDedupe() in reply-payloads.ts.
    """
    trimmed = value.strip()
    if not trimmed:
        return ""
    lower = trimmed.lower()
    if not lower.startswith("file://"):
        return trimmed
    # Strip file:// prefix and URL-decode
    try:
        from urllib.parse import urlparse, unquote
        parsed = urlparse(trimmed)
        if parsed.scheme == "file":
            return unquote(parsed.path or "")
    except Exception:
        pass
    # Fallback: strip prefix
    return re.sub(r"^file://", "", trimmed, flags=re.IGNORECASE)


def filter_messaging_tool_media_duplicates(
    payloads: list[Any],
    sent_media_urls: list[str],
) -> list[Any]:
    """Remove media already sent via messaging tool from payloads.

    Mirrors TS filterMessagingToolMediaDuplicates().
    """
    if not sent_media_urls:
        return payloads
    sent_set = {_normalize_media_for_dedupe(u) for u in sent_media_urls if u}
    sent_set.discard("")

    result = []
    for payload in payloads:
        media_url = getattr(payload, "media_url", None)
        media_urls = getattr(payload, "media_urls", None)
        strip_single = media_url and _normalize_media_for_dedupe(media_url) in sent_set
        filtered_urls = (
            [u for u in media_urls if _normalize_media_for_dedupe(u) not in sent_set]
            if media_urls
            else None
        )
        if not strip_single and (not media_urls or filtered_urls is None or len(filtered_urls) == len(media_urls)):
            result.append(payload)
        else:
            from dataclasses import replace
            try:
                updated = replace(
                    payload,
                    media_url=None if strip_single else media_url,
                    media_urls=filtered_urls if filtered_urls else None,
                )
                result.append(updated)
            except Exception:
                result.append(payload)
    return result


_PROVIDER_ALIAS_MAP: dict[str, str] = {
    "lark": "feishu",
}


def _normalize_provider_for_comparison(value: str | None) -> str | None:
    """Normalize provider/channel ID for comparison.

    Mirrors TS normalizeProviderForComparison() in reply-payloads.ts.
    """
    if not value:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    lowered = trimmed.lower()
    try:
        from openclaw.channels.plugins import normalize_channel_id
        normalized = normalize_channel_id(trimmed)
        if normalized:
            return normalized
    except Exception:
        pass
    return _PROVIDER_ALIAS_MAP.get(lowered, lowered)


def _normalize_target_for_provider(provider: str, target: str | None) -> str | None:
    """Normalize a delivery target (chat_id, phone number etc.) for a provider.

    Simplified version of TS normalizeTargetForProvider().
    """
    if not target:
        return None
    trimmed = target.strip()
    if not trimmed:
        return None
    # Normalize e164 for whatsapp/message providers
    if provider in ("whatsapp", "wa"):
        normalized = re.sub(r"[\s\-\(\)\+]", "", trimmed)
        if normalized.startswith("0"):
            normalized = normalized[1:]
        return normalized.lower()
    return trimmed.lower()


def _normalize_optional_account_id(account_id: str | None) -> str | None:
    """Normalize an account ID for comparison."""
    if not account_id:
        return None
    trimmed = account_id.strip()
    return trimmed.lower() if trimmed else None


def should_suppress_messaging_tool_replies(
    *,
    message_provider: str | None = None,
    messaging_tool_sent_targets: list[Any] | None = None,
    originating_to: str | None = None,
    account_id: str | None = None,
) -> bool:
    """Return True when a messaging tool already delivered to the same destination.

    Mirrors TS shouldSuppressMessagingToolReplies() in reply-payloads.ts.
    """
    provider = _normalize_provider_for_comparison(message_provider)
    if not provider:
        return False
    origin_target = _normalize_target_for_provider(provider, originating_to)
    if not origin_target:
        return False
    origin_account = _normalize_optional_account_id(account_id)
    sent_targets = messaging_tool_sent_targets or []
    if not sent_targets:
        return False
    for target in sent_targets:
        target_provider_raw = (
            target.get("provider") if isinstance(target, dict) else getattr(target, "provider", None)
        )
        target_provider = _normalize_provider_for_comparison(target_provider_raw)
        if not target_provider:
            continue
        is_generic = target_provider == "message"
        if not is_generic and target_provider != provider:
            continue
        normalization_provider = provider if is_generic else target_provider
        target_to_raw = (
            target.get("to") if isinstance(target, dict) else getattr(target, "to", None)
        )
        target_key = _normalize_target_for_provider(normalization_provider, target_to_raw)
        if not target_key:
            continue
        if target_key != origin_target:
            continue
        target_account_raw = (
            target.get("accountId") if isinstance(target, dict) else getattr(target, "accountId", None)
        )
        target_account = _normalize_optional_account_id(target_account_raw)
        if origin_account and target_account and origin_account != target_account:
            continue
        return True
    return False


# ---------------------------------------------------------------------------
# Gap 6 — apply_reply_threading (payload-level)
# ---------------------------------------------------------------------------

_REPLY_TAG_RE = re.compile(
    r"\[\[\s*(?:reply:([^\]\n]+)|reply_to_current|reply_to\s*:\s*([^\]\n]+))\s*\]\]",
    re.IGNORECASE,
)


def _extract_reply_to_tag(text: str, current_message_id: str | None = None) -> dict:
    """Parse and strip [[reply:ID]] / [[reply:current]] tags from text.

    Mirrors TS extractReplyToTag() in reply-tags.ts.
    """
    reply_to_id: str | None = None
    reply_to_current = False
    has_tag = False
    cleaned = text

    def replacer(m: re.Match) -> str:
        nonlocal reply_to_id, reply_to_current, has_tag
        has_tag = True
        g1 = (m.group(1) or "").strip()
        g2 = (m.group(2) or "").strip()
        explicit_id = g1 or g2
        if explicit_id.lower() == "current":
            reply_to_current = True
        elif explicit_id:
            reply_to_id = explicit_id
        else:
            reply_to_current = True
        return " "

    cleaned = _REPLY_TAG_RE.sub(replacer, cleaned).strip()
    if reply_to_current and not reply_to_id and current_message_id:
        reply_to_id = current_message_id.strip()

    return {
        "cleaned": cleaned,
        "reply_to_id": reply_to_id,
        "reply_to_current": reply_to_current,
        "has_tag": has_tag,
    }


def _resolve_reply_threading_for_payload(
    payload: Any,
    implicit_reply_to_id: str | None = None,
    current_message_id: str | None = None,
) -> Any:
    """Apply reply threading steps to a single payload.

    Mirrors TS resolveReplyThreadingForPayload().
    Step 1: apply implicit reply_to_id if payload has none
    Step 2: parse and strip [[reply:…]] tags
    Step 3: if replyToCurrent was set, apply current_message_id
    """
    from dataclasses import replace

    existing_reply_to = getattr(payload, "reply_to_id", None)
    reply_to_current = getattr(payload, "reply_to_current", False)

    # Step 1: implicit threading
    resolved = payload
    if not existing_reply_to and not reply_to_current and implicit_reply_to_id:
        try:
            resolved = replace(resolved, reply_to_id=implicit_reply_to_id)
        except Exception:
            pass

    # Step 2: parse explicit reply tags from text — explicit tags override implicit
    text = getattr(resolved, "text", None)
    if isinstance(text, str) and "[[" in text:
        parsed = _extract_reply_to_tag(text, current_message_id)
        update = {}
        if parsed["cleaned"] != text:
            update["text"] = parsed["cleaned"] if parsed["cleaned"] else None
        # Explicit [[reply:ID]] tag always wins over implicit threading (mirrors TS: replyToId ?? resolved.replyToId)
        if parsed["reply_to_id"]:
            update["reply_to_id"] = parsed["reply_to_id"]
        if update:
            try:
                resolved = replace(resolved, **update)
            except Exception:
                pass

    return resolved


def _is_renderable_payload(payload: Any) -> bool:
    """Return True when a payload has deliverable content."""
    return bool(
        getattr(payload, "text", None)
        or getattr(payload, "media_url", None)
        or (getattr(payload, "media_urls", None) and len(payload.media_urls) > 0)
        or getattr(payload, "audio_as_voice", None)
    )


def _create_reply_to_mode_filter(reply_to_mode: str, channel: str | None = None):
    """Create a function that applies replyToMode policy to a payload.

    Mirrors TS createReplyToModeFilterForChannel().
    """
    mode = (reply_to_mode or "off").lower()

    if mode == "off":
        def _strip_reply(payload: Any) -> Any:
            if getattr(payload, "reply_to_id", None):
                try:
                    from dataclasses import replace
                    return replace(payload, reply_to_id=None)
                except Exception:
                    pass
            return payload
        return _strip_reply

    if mode == "all":
        return lambda p: p  # keep all reply IDs

    # mode == "first" or unknown — only keep the first reply
    first_seen = [False]

    def _first_only(payload: Any) -> Any:
        if getattr(payload, "reply_to_id", None):
            if not first_seen[0]:
                first_seen[0] = True
                return payload
            try:
                from dataclasses import replace
                return replace(payload, reply_to_id=None)
            except Exception:
                pass
        return payload

    return _first_only


def apply_reply_threading(
    payloads: list[Any],
    reply_to_mode: str,
    channel: str | None = None,
    current_message_id: str | None = None,
) -> list[Any]:
    """Apply the 3-step reply threading pipeline to a list of payloads.

    Mirrors TS applyReplyThreading() in reply-payloads.ts.

    Step 1: implicit replyToId from current_message_id
    Step 2: parse [[reply:…]] tags and strip from text
    Step 3: apply per-channel replyToMode policy
    """
    apply_mode = _create_reply_to_mode_filter(reply_to_mode, channel)
    implicit = (current_message_id or "").strip() or None

    result = []
    for payload in payloads:
        resolved = _resolve_reply_threading_for_payload(
            payload,
            implicit_reply_to_id=implicit,
            current_message_id=current_message_id,
        )
        if not _is_renderable_payload(resolved):
            continue
        result.append(apply_mode(resolved))
    return result


__all__ = [
    "filter_messaging_tool_duplicates",
    "filter_messaging_tool_media_duplicates",
    "should_suppress_messaging_tool_replies",
    "apply_reply_threading",
]
