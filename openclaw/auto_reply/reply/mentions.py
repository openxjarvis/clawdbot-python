"""Mention pattern detection and stripping for group chats.

Mirrors TypeScript openclaw/src/auto-reply/reply/mentions.ts.
"""
from __future__ import annotations

import re
from typing import Any, TypedDict


BACKSPACE_CHAR = "\u0008"
CURRENT_MESSAGE_MARKER = "[Current message - respond to this]"


class ExplicitMentionSignal(TypedDict, total=False):
    """Explicit mention signal from channel provider."""
    hasAnyMention: bool
    isExplicitlyMentioned: bool
    canResolveExplicit: bool


def _escape_regex(text: str) -> str:
    """Escape special regex characters.
    
    Mirrors TS escapeRegExp() from utils.ts.
    """
    return re.escape(text)


def _derive_mention_patterns(identity: dict[str, Any] | None) -> list[str]:
    """Derive mention patterns from agent identity (raw strings, not regex).

    Mirrors TS deriveMentionPatterns().
    Returns the raw name/emoji strings so they can be compiled as-is by
    build_mention_regexes().
    """
    patterns: list[str] = []

    if not identity:
        return patterns

    name = (identity.get("name") or "").strip()
    if name:
        patterns.append(name)

    emoji = (identity.get("emoji") or "").strip()
    if emoji:
        patterns.append(emoji)

    return patterns


def _normalize_mention_pattern(pattern: str) -> str:
    """Normalize mention pattern by converting backspace chars to word boundaries.
    
    Mirrors TS normalizeMentionPattern().
    """
    if BACKSPACE_CHAR not in pattern:
        return pattern
    return pattern.replace(BACKSPACE_CHAR, r"\b")


def _normalize_mention_patterns(patterns: list[str]) -> list[str]:
    """Normalize all mention patterns.
    
    Mirrors TS normalizeMentionPatterns().
    """
    return [_normalize_mention_pattern(p) for p in patterns]


def resolve_mention_patterns(
    cfg: dict[str, Any] | None,
    agent_id: str | None = None,
    channel: str | None = None,
    account_id: str | None = None,
    group_id: str | None = None,
) -> list[str]:
    """Resolve mention patterns from config and identity.

    Mirrors TS resolveMentionPatterns().

    Resolution order:
    1. Agent-specific groupChat.mentionPatterns (early return)
    2. Global groupChat.mentionPatterns (cfg.groupChat or cfg.messages.groupChat)
       combined with effective identity patterns
    3. Effective identity-derived patterns only

    Args:
        cfg: OpenClaw configuration
        agent_id: Optional agent ID
        channel: Optional channel ID
        account_id: Optional account ID
        group_id: Optional group ID

    Returns:
        List of mention pattern strings
    """
    if not cfg:
        return []

    # ── Resolve agent config ────────────────────────────────────────────────
    agent_config: dict[str, Any] | None = None
    if agent_id:
        agents = cfg.get("agents") or {}
        if isinstance(agents, dict):
            # Dict format: agents[agent_id]
            candidate = agents.get(agent_id)
            if isinstance(candidate, dict):
                agent_config = candidate
            # Array format: agents.list[...]
            if agent_config is None:
                for a in agents.get("list", []):
                    if isinstance(a, dict) and a.get("id") == agent_id:
                        agent_config = a
                        break

    # ── 1. Agent-specific mentionPatterns (overrides everything) ────────────
    if agent_config:
        agent_gc = agent_config.get("groupChat") or {}
        if isinstance(agent_gc, dict) and "mentionPatterns" in agent_gc:
            return list(agent_gc["mentionPatterns"] or [])

    # ── 2. Global mentionPatterns base + effective identity ─────────────────
    global_gc = (
        cfg.get("groupChat")
        or cfg.get("messages", {}).get("groupChat")
        or {}
    )
    base_patterns: list[str] = list(global_gc.get("mentionPatterns") or []) if isinstance(global_gc, dict) else []

    # Effective identity: agent-specific takes priority over global
    effective_identity: dict[str, Any] | None = None
    if agent_config:
        effective_identity = agent_config.get("identity") or None
    if effective_identity is None and not agent_config:
        # Only fall back to global identity when no agent_config at all
        effective_identity = cfg.get("identity") or None

    derived = _derive_mention_patterns(effective_identity)

    if base_patterns or derived:
        return base_patterns + [p for p in derived if p not in base_patterns]

    return []


def build_mention_regexes(
    cfg: dict[str, Any] | None,
    agent_id: str | None = None,
    patterns: list[str] | None = None,
    identity: dict[str, Any] | None = None,
) -> list[re.Pattern[str]]:
    """Build compiled regex patterns for mention detection.
    
    Mirrors TS buildMentionRegexes().
    
    Args:
        cfg: OpenClaw configuration
        agent_id: Optional agent ID
        patterns: Optional explicit patterns (overrides config resolution)
        identity: Optional identity for pattern derivation
        
    Returns:
        List of compiled regex patterns (case-insensitive)
    """
    if patterns is None:
        if identity:
            patterns = _derive_mention_patterns(identity)
        else:
            patterns = resolve_mention_patterns(cfg, agent_id)
    
    normalized = _normalize_mention_patterns(patterns)
    regexes: list[re.Pattern[str]] = []
    
    for pattern in normalized:
        try:
            regexes.append(re.compile(pattern, re.IGNORECASE))
        except re.error:
            # Ignore invalid regex patterns
            pass
    
    return regexes


def normalize_mention_text(text: str) -> str:
    """Normalize text for mention matching by removing invisible/control characters.

    Mirrors TS normalizeMentionText().

    Removes:
    - Backspace (U+0008)
    - Unicode zero-width and formatting characters (U+200B–U+200F, U+202A–U+202E, U+2060–U+206F)

    Args:
        text: Text to normalize

    Returns:
        Normalized lowercase text
    """
    if not text:
        return ""
    # Remove backspace and zero-width/formatting characters
    cleaned = re.sub(r"[\u0008\u200b-\u200f\u202a-\u202e\u2060-\u206f]", "", text)
    return cleaned.lower()


def matches_mention_patterns(text: str, mention_regexes: list[re.Pattern[str]]) -> bool:
    """Check if text matches any mention pattern.
    
    Mirrors TS matchesMentionPatterns().
    
    Args:
        text: Text to check
        mention_regexes: Compiled mention regex patterns
        
    Returns:
        True if text matches any pattern
    """
    if not mention_regexes:
        return False
    
    cleaned = normalize_mention_text(text or "")
    if not cleaned:
        return False
    
    return any(regex.search(cleaned) for regex in mention_regexes)


def matches_mention_with_explicit(
    text: str,
    mention_regexes: list[re.Pattern[str]],
    explicit: ExplicitMentionSignal | None = None,
    transcript: str | None = None,
) -> bool:
    """Check if text matches mention with explicit signal support.
    
    Mirrors TS matchesMentionWithExplicit().
    
    Combines pattern-based mention detection with explicit mention signals
    from channel providers (e.g., Telegram @mentions, WhatsApp @mentions).
    
    Args:
        text: Text to check
        mention_regexes: Compiled mention regex patterns
        explicit: Optional explicit mention signal from provider
        transcript: Optional transcript text (used if text is empty)
        
    Returns:
        True if explicitly mentioned or text matches patterns
    """
    cleaned = normalize_mention_text(text or "")
    
    is_explicit = bool(explicit.get("isExplicitlyMentioned", False)) if explicit else False
    explicit_available = bool(explicit.get("canResolveExplicit", False)) if explicit else False

    # When the channel CAN resolve explicit mentions, trust it completely —
    # don't fall through to pattern matching (mirrors TS behaviour).
    if explicit_available:
        return is_explicit

    # Fall back to pattern matching when explicit signal unavailable
    transcript_cleaned = normalize_mention_text(transcript) if transcript else ""
    text_to_check = cleaned or transcript_cleaned

    if not text_to_check:
        return is_explicit

    return is_explicit or any(regex.search(text_to_check) for regex in mention_regexes)


def strip_structural_prefixes(text: str) -> str:
    """Strip structural prefixes from text for directive detection.
    
    Mirrors TS stripStructuralPrefixes().
    
    Removes:
    - Wrapper labels like [Current message - respond to this]
    - Timestamps and sender prefixes (e.g., "Alice: ")
    - Brackets and their contents
    
    Args:
        text: Text to clean
        
    Returns:
        Cleaned text
    """
    # Remove everything before current message marker
    if CURRENT_MESSAGE_MARKER in text:
        after_marker = text[text.index(CURRENT_MESSAGE_MARKER) + len(CURRENT_MESSAGE_MARKER):]
        text = after_marker.lstrip()
    
    # Remove bracketed content
    text = re.sub(r"\[[^\]]+\]\s*", "", text)
    
    # Remove sender prefixes (e.g., "Alice: ", "User123: ")
    text = re.sub(r"^[ \t]*[A-Za-z0-9+()\-_. ]+:\s*", "", text, flags=re.MULTILINE)
    
    # Normalize whitespace
    text = text.replace("\\n", " ")
    text = re.sub(r"\s+", " ", text)
    
    return text.strip()


def strip_mentions(
    text: str,
    mention_regexes: list[re.Pattern[str]] | None = None,
    cfg: dict[str, Any] | None = None,
    agent_id: str | None = None,
    ctx: dict[str, Any] | None = None,
) -> str:
    """Strip mention patterns from text.
    
    Mirrors TS stripMentions().
    
    Removes:
    - Configured mention patterns
    - Provider-specific mention patterns
    - Generic @mentions with numeric IDs (@123456789)
    
    Args:
        text: Text to process
        mention_regexes: Optional pre-compiled mention regexes
        cfg: Optional OpenClaw configuration
        agent_id: Optional agent ID
        ctx: Optional message context
        
    Returns:
        Text with mentions stripped
    """
    result = text
    
    # Build regexes if not provided
    if mention_regexes is None:
        patterns = resolve_mention_patterns(cfg, agent_id)
        normalized = _normalize_mention_patterns(patterns)
    else:
        normalized = [regex.pattern for regex in mention_regexes]
    
    # Strip configured patterns
    for pattern in normalized:
        try:
            regex = re.compile(pattern, re.IGNORECASE)
            result = regex.sub(" ", result)
        except re.error:
            # Ignore invalid regex
            pass
    
    # Strip generic @mentions with numeric IDs
    result = re.sub(r"@[0-9+]{5,}", " ", result)
    
    # Normalize whitespace
    result = re.sub(r"\s+", " ", result)
    
    return result.strip()


__all__ = [
    "BACKSPACE_CHAR",
    "CURRENT_MESSAGE_MARKER",
    "ExplicitMentionSignal",
    "resolve_mention_patterns",
    "build_mention_regexes",
    "normalize_mention_text",
    "matches_mention_patterns",
    "matches_mention_with_explicit",
    "strip_structural_prefixes",
    "strip_mentions",
]
