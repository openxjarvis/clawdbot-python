"""Feishu (Lark) extension — registers Feishu channel and agent tools.

Mirrors TypeScript: openclaw/extensions/feishu/index.ts

Registers:
- Feishu messaging channel (FeishuChannel)
- Feishu Doc / Wiki / Drive / Bitable / Chat / Perm tools
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def register(api) -> None:
    # ---- Channel ----
    try:
        from openclaw.channels.feishu.channel import FeishuChannel

        api.register_channel(FeishuChannel())
        logger.info("Feishu channel registered")
    except ImportError:
        logger.warning(
            "Feishu channel unavailable — install optional Feishu dependencies: "
            "pip install 'openclaw-python[feishu]'"
        )

    # ---- Agent Tools ----
    _register_tools(api)


def _register_tools(api) -> None:
    """Register Feishu-specific agent tools. Mirrors TS index.ts tool registrations."""
    try:
        from openclaw.channels.feishu.tools.feishu_chat import (
            TOOL_NAME as CHAT_NAME,
            TOOL_DESCRIPTION as CHAT_DESC,
            TOOL_SCHEMA as CHAT_SCHEMA,
            run_feishu_chat,
        )
        from openclaw.channels.feishu.tools.feishu_doc import (
            TOOL_NAME as DOC_NAME,
            TOOL_DESCRIPTION as DOC_DESC,
            TOOL_SCHEMA as DOC_SCHEMA,
            run_feishu_doc,
        )
        from openclaw.channels.feishu.tools.feishu_wiki import (
            TOOL_NAME as WIKI_NAME,
            TOOL_DESCRIPTION as WIKI_DESC,
            TOOL_SCHEMA as WIKI_SCHEMA,
            run_feishu_wiki,
        )
        from openclaw.channels.feishu.tools.feishu_drive import (
            TOOL_NAME as DRIVE_NAME,
            TOOL_DESCRIPTION as DRIVE_DESC,
            TOOL_SCHEMA as DRIVE_SCHEMA,
            run_feishu_drive,
        )
        from openclaw.channels.feishu.tools.feishu_bitable import (
            TOOL_NAME as BITABLE_NAME,
            TOOL_DESCRIPTION as BITABLE_DESC,
            TOOL_SCHEMA as BITABLE_SCHEMA,
            run_feishu_bitable,
        )
        from openclaw.channels.feishu.tools.feishu_perm import (
            TOOL_NAME as PERM_NAME,
            TOOL_DESCRIPTION as PERM_DESC,
            TOOL_SCHEMA as PERM_SCHEMA,
            run_feishu_perm,
        )
        from openclaw.channels.feishu.tools.feishu_reactions import (
            TOOL_NAME as REACTIONS_NAME,
            TOOL_DESCRIPTION as REACTIONS_DESC,
            TOOL_SCHEMA as REACTIONS_SCHEMA,
            run_feishu_reactions,
        )
        from openclaw.channels.feishu.tools.feishu_calendar import (
            TOOL_NAME as CALENDAR_NAME,
            TOOL_DESCRIPTION as CALENDAR_DESC,
            TOOL_SCHEMA as CALENDAR_SCHEMA,
            run_feishu_calendar,
        )

        _tools = [
            (CHAT_NAME, CHAT_DESC, CHAT_SCHEMA, run_feishu_chat),
            (DOC_NAME, DOC_DESC, DOC_SCHEMA, run_feishu_doc),
            (WIKI_NAME, WIKI_DESC, WIKI_SCHEMA, run_feishu_wiki),
            (DRIVE_NAME, DRIVE_DESC, DRIVE_SCHEMA, run_feishu_drive),
            (BITABLE_NAME, BITABLE_DESC, BITABLE_SCHEMA, run_feishu_bitable),
            (PERM_NAME, PERM_DESC, PERM_SCHEMA, run_feishu_perm),
            (REACTIONS_NAME, REACTIONS_DESC, REACTIONS_SCHEMA, run_feishu_reactions),
            (CALENDAR_NAME, CALENDAR_DESC, CALENDAR_SCHEMA, run_feishu_calendar),
        ]

        if hasattr(api, "register_tool"):
            for name, desc, schema, handler in _tools:
                api.register_tool(name=name, description=desc, schema=schema, handler=handler)
            logger.info("Feishu tools registered: %s", [t[0] for t in _tools])
        else:
            logger.debug("api.register_tool not available — skipping Feishu tool registration")

    except ImportError as e:
        logger.debug("Feishu tools not registered (missing deps): %s", e)
    except Exception as e:
        logger.warning("Failed to register Feishu tools: %s", e)


plugin = {
    "id": "feishu",
    "name": "Feishu",
    "description": "Feishu/Lark channel plugin with Doc, Wiki, Drive, Perm, Bitable, Chat, Calendar, and Reactions tools.",
    "register": register,
}
