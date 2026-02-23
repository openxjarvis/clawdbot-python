"""Slash-command handlers for the auto-reply system.

Port of TypeScript commands-*.ts files in openclaw/src/auto-reply/reply/.

Each command group lives in its own module:
  commands_info     → /help, /commands, /status, /context, /whoami, /export-session
  commands_session  → /new, /reset, /compact, /session
  commands_model    → /model, /models, /think, /verbose, /reasoning
  commands_config   → /config, set, unset, /system-prompt
  commands_tools    → /bash, /subagents, /allowlist, /ptt, /tts, /debug

The `dispatch_command` function routes to the correct handler.
"""
from __future__ import annotations

import logging
from typing import Any

from ..get_reply import ReplyPayload

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Command dispatch table
# ---------------------------------------------------------------------------

_SESSION_CMDS = {"new", "reset", "compact", "session", "clear"}
_INFO_CMDS = {
    "help", "commands", "status", "context", "context-report",
    "whoami", "export-session", "export", "debug",
}
_MODEL_CMDS = {"model", "models", "think", "verbose", "reasoning"}
_CONFIG_CMDS = {"config", "set", "unset", "system-prompt"}
_TOOLS_CMDS = {"bash", "shell", "subagents", "allowlist", "approve", "ptt", "tts", "plugin"}


async def dispatch_command(
    command_name: str,
    args_text: str,
    ctx: Any,
    cfg: dict[str, Any],
    session_key: str,
    runtime: Any,
) -> ReplyPayload | None:
    """Route a slash command to its handler module."""
    name = command_name.lower()

    try:
        if name in _SESSION_CMDS:
            from .commands_session import handle_session_command
            return await handle_session_command(name, args_text, ctx, cfg, session_key, runtime)

        if name in _INFO_CMDS:
            from .commands_info import handle_info_command
            return await handle_info_command(name, args_text, ctx, cfg, session_key, runtime)

        if name in _MODEL_CMDS:
            from .commands_model import handle_model_command
            return await handle_model_command(name, args_text, ctx, cfg, session_key, runtime)

        if name in _CONFIG_CMDS:
            from .commands_config import handle_config_command
            return await handle_config_command(name, args_text, ctx, cfg, session_key, runtime)

        if name in _TOOLS_CMDS:
            from .commands_tools import handle_tools_command
            return await handle_tools_command(name, args_text, ctx, cfg, session_key, runtime)

    except Exception as exc:
        logger.warning(f"dispatch_command: /{command_name} failed: {exc}", exc_info=True)
        return ReplyPayload(text=f"Command failed: {exc}")

    return None
