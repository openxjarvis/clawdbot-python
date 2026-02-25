"""Group chat context building functions.

Mirrors TypeScript openclaw/src/auto-reply/reply/groups.ts.
"""
from __future__ import annotations

from typing import Any

from openclaw.auto_reply.group_activation import GroupActivationMode, normalize_group_activation


def _extract_group_id(raw: str | None) -> str | None:
    """Extract group ID from session key or raw string.
    
    Mirrors TS extractGroupId().
    """
    trimmed = (raw or "").strip()
    if not trimmed:
        return None
    
    parts = [p for p in trimmed.split(":") if p]
    
    # Format: agent:agentId:channel:group:groupId or agent:agentId:channel:channel:channelId
    if len(parts) >= 3 and parts[1] in ("group", "channel"):
        return ":".join(parts[2:]) or None
    
    # WhatsApp format: whatsapp:123456789@g.us
    if len(parts) >= 2 and parts[0].lower() == "whatsapp" and "@g.us" in trimmed.lower():
        return ":".join(parts[1:]) or None
    
    # Format: group:groupId or channel:channelId
    if len(parts) >= 2 and parts[0] in ("group", "channel"):
        return ":".join(parts[1:]) or None
    
    return trimmed


_PROVIDER_LABELS: dict[str, str] = {
    "whatsapp": "WhatsApp",
    "telegram": "Telegram",
    "discord": "Discord",
    "slack": "Slack",
    "signal": "Signal",
    "webchat": "WebChat",
    "message": "WebChat",
    "internal": "WebChat",
}


def _resolve_provider_label(raw_provider: str | None) -> str:
    """Resolve human-readable provider label.

    Mirrors TS resolveProviderLabel().
    """
    provider_key = (raw_provider or "").strip().lower()

    if not provider_key:
        return "chat"

    if provider_key in _PROVIDER_LABELS:
        return _PROVIDER_LABELS[provider_key]

    # Capitalize first letter as fallback
    return provider_key[0].upper() + provider_key[1:]


def build_group_chat_context(
    session_ctx: dict[str, Any],
    group_subject: str | None = None,
    group_members: str | None = None,
    provider: str | None = None,
) -> str:
    """Build persistent group chat context for system prompt.
    
    Mirrors TS buildGroupChatContext().
    
    This context is included in every turn (not just first turn) to remind
    the agent about the group chat environment and participants.
    
    Args:
        session_ctx: Session context dict
        group_subject: Optional group subject/name
        group_members: Optional formatted member list
        provider: Optional provider/channel name
        
    Returns:
        Formatted group chat context string
    """
    subject = group_subject or session_ctx.get("GroupSubject", "").strip()
    members = group_members or session_ctx.get("GroupMembers", "").strip()
    provider_raw = provider or session_ctx.get("Provider", "").strip()
    provider_label = _resolve_provider_label(provider_raw)
    
    lines: list[str] = []
    
    if subject:
        lines.append(f'You are in the {provider_label} group chat "{subject}".')
    else:
        lines.append(f"You are in a {provider_label} group chat.")
    
    if members:
        lines.append(f"Participants: {members}.")
    
    lines.append(
        "Your replies are automatically sent to this group chat. "
        "Do not use the message tool to send to this same group — just reply normally."
    )
    
    return " ".join(lines)


def build_group_intro(
    cfg: dict[str, Any],
    session_ctx: dict[str, Any],
    session_entry: dict[str, Any] | None = None,
    default_activation: GroupActivationMode = "mention",
    silent_token: str = "[SILENT]",
) -> str:
    """Build first-turn group activation intro message.
    
    Mirrors TS buildGroupIntro().
    
    This intro is shown only on the first turn of a group session to explain
    activation mode, silence token, and group chat behavior.
    
    Args:
        cfg: OpenClaw configuration
        session_ctx: Session context dict
        session_entry: Optional session entry with groupActivation
        default_activation: Default activation mode
        silent_token: Token for silent responses
        
    Returns:
        Formatted group intro string
    """
    # Resolve activation mode
    activation = default_activation
    if session_entry:
        group_activation = session_entry.get("groupActivation")
        normalized = normalize_group_activation(group_activation)
        if normalized:
            activation = normalized
    
    # Build activation line
    if activation == "always":
        activation_line = "Activation: always-on (you receive every group message)."
    else:
        activation_line = (
            "Activation: trigger-only (you are invoked only when explicitly mentioned; "
            "recent context may be included)."
        )
    
    # Build silence line (only for always-on)
    silence_line: str | None = None
    if activation == "always":
        silence_line = (
            f'If no response is needed, reply with exactly "{silent_token}" '
            "(and nothing else) so OpenClaw stays silent. "
            "Do not add any other words, punctuation, tags, markdown/code blocks, or explanations."
        )
    
    # Build caution line (only for always-on)
    caution_line: str | None = None
    if activation == "always":
        caution_line = (
            "Be extremely selective: reply only when directly addressed or clearly helpful. "
            "Otherwise stay silent."
        )
    
    # Build lurk line
    lurk_line = (
        "Be a good group participant: mostly lurk and follow the conversation; "
        "reply only when directly addressed or you can add clear value. "
        "Emoji reactions are welcome when available."
    )
    
    # Build style line
    style_line = (
        "Write like a human. Avoid Markdown tables. "
        "Don't type literal \\n sequences; use real line breaks sparingly."
    )
    
    # Combine all lines
    parts = [
        activation_line,
        silence_line,
        caution_line,
        lurk_line,
        style_line,
    ]
    
    result = " ".join(part for part in parts if part)
    result += " Address the specific sender noted in the message context."
    
    return result


def format_group_members(
    members: list[dict[str, Any]] | dict[str, str],
    max_members: int | None = None,
    separator: str = ", ",
) -> str:
    """Format group members for context display.

    Mirrors TS formatGroupMembers() concept.

    Args:
        members: List of member dicts or dict mapping IDs to names
        max_members: Optional maximum number of members to show
        separator: Separator between member names

    Returns:
        Formatted member list string
    """
    if isinstance(members, dict):
        names = list(members.values())
    elif isinstance(members, list):
        names = [m.get("name", m.get("id", "Unknown")) for m in members if isinstance(m, dict)]
    else:
        return ""

    if not names:
        return ""

    truncated = False
    if max_members is not None and len(names) > max_members:
        names = names[:max_members]
        truncated = True

    result = separator.join(names)
    if truncated:
        result += f"{separator}..."

    return result


__all__ = [
    "build_group_chat_context",
    "build_group_intro",
    "format_group_members",
]
