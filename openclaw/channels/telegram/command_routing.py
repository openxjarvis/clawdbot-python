"""Telegram command routing and session resolution.

Fully aligned with TypeScript openclaw/src/telegram/bot-native-commands.ts resolveCommandRuntimeContext
"""
from __future__ import annotations

import logging
from typing import Any, TypedDict

from telegram import Update

logger = logging.getLogger(__name__)


class ThreadSpec(TypedDict):
    """Thread specification."""
    scope: str  # "dm" | "group" | "forum"
    id: int


class CommandRuntimeContext(TypedDict):
    """Command runtime context."""
    thread_spec: ThreadSpec
    agent_id: str
    session_key: str
    media_local_roots: list[str]
    table_mode: str
    chunk_mode: str


def resolve_command_runtime_context(
    update: Update,
    cfg: dict[str, Any],
    account_id: str,
    auth: dict[str, Any],
) -> CommandRuntimeContext:
    """Resolve command runtime context (mirrors TS resolveCommandRuntimeContext).
    
    Args:
        update: Telegram update
        cfg: OpenClaw configuration
        account_id: Telegram account ID
        auth: Authentication result
        
    Returns:
        Runtime context with routing info
    """
    msg = update.message or update.edited_message
    if not msg:
        raise ValueError("Message is required")
    
    chat_id = auth["chat_id"]
    is_group = auth["is_group"]
    is_forum = auth["is_forum"]
    resolved_thread_id = auth["resolved_thread_id"]
    
    # Resolve thread spec
    if is_group:
        if is_forum and resolved_thread_id:
            thread_spec = ThreadSpec(scope="forum", id=resolved_thread_id)
        else:
            thread_spec = ThreadSpec(scope="group", id=chat_id)
    else:
        thread_spec = ThreadSpec(scope="dm", id=chat_id)
    
    # Resolve agent route
    from openclaw.routing.resolve_route import resolve_agent_route
    
    peer_kind = "group" if is_group else "direct"
    peer_id = str(resolved_thread_id) if (is_forum and resolved_thread_id) else str(chat_id)
    
    route = resolve_agent_route(
        cfg=cfg,
        channel="telegram",
        account_id=account_id,
        peer={
            "kind": peer_kind,
            "id": peer_id,
        }
    )
    
    agent_id = route.agent_id if hasattr(route, "agent_id") else "main"
    
    # Use session_key from resolved route (it applies dmScope and identity links)
    # Fallback to manual construction if needed
    session_key = route.session_key if hasattr(route, "session_key") and route.session_key else \
        f"agent:{agent_id}:telegram:{peer_kind}:{peer_id}"
    
    # Get media and display settings
    telegram_cfg = cfg.get("channels", {}).get("telegram", {})
    account_cfg = telegram_cfg.get("accounts", {}).get(account_id, {})
    
    media_local_roots = account_cfg.get("media_local_roots", [])
    table_mode = account_cfg.get("table_mode", "markdown")
    chunk_mode = account_cfg.get("chunk_mode", "auto")
    
    return CommandRuntimeContext(
        thread_spec=thread_spec,
        agent_id=agent_id,
        session_key=session_key,
        media_local_roots=media_local_roots,
        table_mode=table_mode,
        chunk_mode=chunk_mode,
    )


__all__ = [
    "ThreadSpec",
    "CommandRuntimeContext",
    "resolve_command_runtime_context",
]
