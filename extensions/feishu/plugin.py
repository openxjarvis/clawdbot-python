"""Feishu (Lark) extension — registers Feishu channel and document tools.

Mirrors TypeScript: openclaw/extensions/feishu/index.ts

Registers:
- Feishu messaging channel
- Feishu Doc / Wiki / Drive / Perm / Bitable tools
"""
from __future__ import annotations



def register(api) -> None:
    try:
        from openclaw.channels.feishu.channel import FeishuChannel

        api.register_channel(FeishuChannel())
    except ImportError:
        import logging

        logging.getLogger(__name__).warning(
            "Feishu channel unavailable — install optional Feishu dependencies"
        )

    # Register Feishu tools (Doc, Wiki, Drive, Perm, Bitable)
    # TODO: implement tool registrations — see openclaw/extensions/feishu/src/*.ts

plugin = {
    "id": "feishu",
    "name": "Feishu",
    "description": "Feishu/Lark channel plugin with Doc, Wiki, Drive, Perm, and Bitable tools.",
    "register": register,
}
