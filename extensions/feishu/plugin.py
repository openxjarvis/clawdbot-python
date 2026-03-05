"""Feishu (Lark) plugin — registers Feishu channel and all agent tools.

Mirrors: clawdbot-feishu/index.ts

Tool groups (matches clawdbot-feishu/src/ structure):
    src/tools/doc_tools/      feishu_doc (13 actions) + feishu_app_scopes
    src/tools/wiki_tools/     feishu_wiki (7 actions)
    src/tools/drive_tools/    feishu_drive (6 actions)
    src/tools/perm_tools/     feishu_perm (3 actions, disabled by default)
    src/tools/bitable_tools/  11 feishu_bitable_* individual tools
    src/tools/task_tools/     23 feishu_task_* / feishu_tasklist_* individual tools
    src/tools/urgent_tools/   feishu_urgent
    flat files:               feishu_chat (10 actions), feishu_reactions, feishu_calendar

Skills: extensions/feishu/skills/ (copied from clawdbot-feishu/skills/)
"""
from __future__ import annotations

import logging
import os
import sys

# Make `extensions/feishu/` importable as a package root so that
# `from src.tools.xxx import ...` resolves correctly regardless of how the
# plugin loader sets up sys.path.
_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
if _PLUGIN_DIR not in sys.path:
    sys.path.insert(0, _PLUGIN_DIR)

logger = logging.getLogger(__name__)


def register(api) -> None:
    """Entry point called by the plugin loader."""
    # ── Channel ──────────────────────────────────────────────────────────
    try:
        from openclaw.channels.feishu.channel import FeishuChannel
        api.register_channel(FeishuChannel())
        logger.info("Feishu channel registered")
    except ImportError:
        logger.warning(
            "Feishu channel unavailable — install optional deps: "
            "pip install 'openclaw-python[feishu]'"
        )

    # ── Tools ─────────────────────────────────────────────────────────────
    _register_tools(api)


def _register_tools(api) -> None:
    """Register all Feishu tool groups. Mirrors TS index.ts register() calls."""
    try:
        # Doc tools: feishu_doc + feishu_app_scopes
        from src.tools.doc_tools.register import register_doc_tools
        register_doc_tools(api)
    except Exception as e:
        logger.warning("Failed to register doc tools: %s", e)

    try:
        # Wiki tools: feishu_wiki
        from src.tools.wiki_tools.register import register_wiki_tools
        register_wiki_tools(api)
    except Exception as e:
        logger.warning("Failed to register wiki tools: %s", e)

    try:
        # Drive tools: feishu_drive
        from src.tools.drive_tools.register import register_drive_tools
        register_drive_tools(api)
    except Exception as e:
        logger.warning("Failed to register drive tools: %s", e)

    try:
        # Perm tools: feishu_perm (sensitive — disabled by default in TS too)
        from src.tools.perm_tools.register import register_perm_tools
        register_perm_tools(api)
    except Exception as e:
        logger.warning("Failed to register perm tools: %s", e)

    try:
        # Bitable tools: 11 individual feishu_bitable_* tools
        from src.tools.bitable_tools.register import register_bitable_tools
        register_bitable_tools(api)
    except Exception as e:
        logger.warning("Failed to register bitable tools: %s", e)

    try:
        # Task tools: 23 feishu_task_* / feishu_tasklist_* tools
        from src.tools.task_tools.register import register_task_tools
        register_task_tools(api)
    except Exception as e:
        logger.warning("Failed to register task tools: %s", e)

    try:
        # Urgent tools: feishu_urgent
        from src.tools.urgent_tools.register import register_urgent_tools
        register_urgent_tools(api)
    except Exception as e:
        logger.warning("Failed to register urgent tools: %s", e)

    # Flat-file tools (Python-specific additions not in clawdbot-feishu separate dirs)
    _register_flat_tools(api)


def _register_flat_tools(api) -> None:
    """Register feishu_chat, feishu_reactions, feishu_calendar."""
    _flat = []
    try:
        from src.tools.feishu_chat import (
            TOOL_NAME as CHAT_NAME,
            TOOL_DESCRIPTION as CHAT_DESC,
            TOOL_SCHEMA as CHAT_SCHEMA,
            run_feishu_chat,
        )
        _flat.append((CHAT_NAME, CHAT_DESC, CHAT_SCHEMA, run_feishu_chat))
    except ImportError as e:
        logger.debug("feishu_chat not available: %s", e)

    try:
        from src.tools.feishu_reactions import (
            TOOL_NAME as REACTIONS_NAME,
            TOOL_DESCRIPTION as REACTIONS_DESC,
            TOOL_SCHEMA as REACTIONS_SCHEMA,
            run_feishu_reactions,
        )
        _flat.append((REACTIONS_NAME, REACTIONS_DESC, REACTIONS_SCHEMA, run_feishu_reactions))
    except ImportError as e:
        logger.debug("feishu_reactions not available: %s", e)

    try:
        from src.tools.feishu_calendar import (
            TOOL_NAME as CALENDAR_NAME,
            TOOL_DESCRIPTION as CALENDAR_DESC,
            TOOL_SCHEMA as CALENDAR_SCHEMA,
            run_feishu_calendar,
        )
        _flat.append((CALENDAR_NAME, CALENDAR_DESC, CALENDAR_SCHEMA, run_feishu_calendar))
    except ImportError as e:
        logger.debug("feishu_calendar not available: %s", e)

    if hasattr(api, "register_tool"):
        for name, desc, schema, handler in _flat:
            try:
                api.register_tool(name=name, description=desc, schema=schema, handler=handler)
            except Exception as e:
                logger.warning("Failed to register flat tool %s: %s", name, e)
        if _flat:
            logger.info("Registered flat tools: %s", [t[0] for t in _flat])


plugin = {
    "id": "feishu",
    "name": "Feishu",
    "description": (
        "Feishu/Lark channel plugin with full API tool suite: "
        "Doc (13 actions), Wiki (7), Drive (6), Perm (3), "
        "Bitable (11 tools), Task (23 tools), Urgent, Chat, Reactions, Calendar."
    ),
    "register": register,
}
