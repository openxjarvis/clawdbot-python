"""ACP event/prompt mapping utilities — mirrors src/acp/event-mapper.ts"""
from __future__ import annotations

from typing import Any


def extract_text_from_prompt(prompt: list[dict]) -> str:
    """Extract plain text from an ACP ContentBlock list."""
    parts: list[str] = []
    for block in prompt:
        btype = block.get("type")
        if btype == "text":
            text = block.get("text")
            if text:
                parts.append(text)
        elif btype == "resource":
            resource = block.get("resource") or {}
            if isinstance(resource, dict):
                text = resource.get("text")
                if text:
                    parts.append(text)
        elif btype == "resource_link":
            title = block.get("title", "")
            uri = block.get("uri", "")
            title_part = f" ({title})" if title else ""
            line = f"[Resource link{title_part}] {uri}" if uri else f"[Resource link{title_part}]"
            parts.append(line)
    return "\n".join(parts)


def extract_attachments_from_prompt(prompt: list[dict]) -> list[dict]:
    """Extract image attachments from an ACP ContentBlock list."""
    attachments: list[dict] = []
    for block in prompt:
        if block.get("type") != "image":
            continue
        data = block.get("data")
        mime_type = block.get("mimeType")
        if not data or not mime_type:
            continue
        attachments.append({
            "type": "image",
            "mimeType": mime_type,
            "content": data,
        })
    return attachments


def format_tool_title(name: str | None, args: dict | None) -> str:
    """Build a human-readable tool title with argument preview."""
    base = name or "tool"
    if not args:
        return base
    parts: list[str] = []
    for key, value in args.items():
        raw = value if isinstance(value, str) else str(value)
        safe = raw[:100] + "..." if len(raw) > 100 else raw
        parts.append(f"{key}: {safe}")
    return f"{base}: {', '.join(parts)}"


def infer_tool_kind(name: str | None) -> str:
    """Infer the tool kind from the tool name for ACP tool call reporting."""
    if not name:
        return "other"
    n = name.lower()
    if "read" in n:
        return "read"
    if "write" in n or "edit" in n:
        return "edit"
    if "delete" in n or "remove" in n:
        return "delete"
    if "move" in n or "rename" in n:
        return "move"
    if "search" in n or "find" in n:
        return "search"
    if "exec" in n or "run" in n or "bash" in n:
        return "execute"
    if "fetch" in n or "http" in n:
        return "fetch"
    return "other"
