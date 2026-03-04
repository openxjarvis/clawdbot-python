"""@mention extraction, stripping, and formatting for Feishu.

Mirrors TypeScript: extensions/feishu/src/mention.ts
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class FeishuMention:
    """A single @mention in a Feishu message."""
    key: str        # internal mention key, e.g. "@_user_1"
    open_id: str    # ou_xxx or similar
    name: str       # display name
    tenant_key: str = ""


# ---------------------------------------------------------------------------
# Mention parsing from SDK event
# ---------------------------------------------------------------------------

def parse_mentions(mentions_raw: list[Any] | None) -> list[FeishuMention]:
    """
    Parse mention objects from the Feishu message event.

    Feishu SDK puts mentions under event.message.mentions as a list of
    MentionEvent objects with fields: key, id (UserID), name, tenant_key.
    """
    if not mentions_raw:
        return []
    result: list[FeishuMention] = []
    for m in mentions_raw:
        if hasattr(m, "key"):
            # SDK object
            mention_id = m.id if hasattr(m, "id") else None
            open_id = ""
            if mention_id:
                open_id = (
                    getattr(mention_id, "open_id", None) or
                    getattr(mention_id, "union_id", None) or
                    getattr(mention_id, "user_id", None) or ""
                )
            result.append(FeishuMention(
                key=getattr(m, "key", ""),
                open_id=open_id,
                name=getattr(m, "name", ""),
                tenant_key=getattr(m, "tenant_key", ""),
            ))
        elif isinstance(m, dict):
            mention_id = m.get("id") or {}
            if isinstance(mention_id, dict):
                open_id = (
                    mention_id.get("open_id") or
                    mention_id.get("union_id") or
                    mention_id.get("user_id") or ""
                )
            else:
                open_id = ""
            result.append(FeishuMention(
                key=m.get("key", ""),
                open_id=open_id,
                name=m.get("name", ""),
                tenant_key=m.get("tenant_key", ""),
            ))
    return result


# ---------------------------------------------------------------------------
# Message body extraction (strips @mentions)
# ---------------------------------------------------------------------------

def extract_message_body(
    text: str,
    mentions: list[FeishuMention],
    *,
    bot_open_id: str | None = None,
) -> str:
    """
    Extract clean message text by removing @bot mention tags.

    Feishu places @mentions as literal @_user_N tokens in the content string.
    Mirrors TS extractMessageBody().
    """
    if not text:
        return ""

    result = text

    for mention in mentions:
        # Replace the key placeholder (e.g. @_user_1) with the display name
        # or remove if it's the bot itself
        if mention.key:
            if bot_open_id and mention.open_id == bot_open_id:
                result = result.replace(mention.key, "")
            else:
                # Replace with @Name for context
                result = result.replace(mention.key, f"@{mention.name}")

    return result.strip()


# ---------------------------------------------------------------------------
# Bot mention detection
# ---------------------------------------------------------------------------

def extract_mention_targets(mentions: list[FeishuMention]) -> list[str]:
    """Return list of open_ids that are @mentioned."""
    return [m.open_id for m in mentions if m.open_id]


def is_bot_mentioned(
    mentions: list[FeishuMention],
    bot_open_id: str,
) -> bool:
    """
    Return True if the bot's open_id appears in the mention list.

    Mirrors TS isBotMentioned().
    """
    normalized_bot = bot_open_id.strip().lower()
    for m in mentions:
        if m.open_id.strip().lower() == normalized_bot:
            return True
    return False


# ---------------------------------------------------------------------------
# Outbound @mention formatting
# ---------------------------------------------------------------------------

def format_mention_text(open_id: str, name: str = "") -> str:
    """
    Format an @mention for plain text (Post) messages.

    Mirrors TS formatMentionText().
    Example: <at user_id="ou_xxx">Name</at>
    """
    return f'<at user_id="{open_id}">{name}</at>'


def format_mention_card(open_id: str) -> str:
    """
    Format an @mention for interactive card (Markdown element) messages.

    Mirrors TS formatMentionCard().
    Example: <at id=ou_xxx></at>
    """
    return f"<at id={open_id}></at>"


# ---------------------------------------------------------------------------
# Escape helper for regex patterns
# ---------------------------------------------------------------------------

def escape_regexp(s: str) -> str:
    """Escape a string for use in a regex pattern."""
    return re.escape(s)


# ---------------------------------------------------------------------------
# Mention forward request detection
# ---------------------------------------------------------------------------

def is_mention_forward_request(text: str) -> bool:
    """
    Detect if the message is a forwarded mention request (system-level).

    Mirrors TS isMentionForwardRequest() — checks for Feishu system message marker.
    """
    return "@_user_" in text and "[" in text and "]" in text
