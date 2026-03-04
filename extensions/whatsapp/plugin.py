"""WhatsApp channel plugin.

Uses Baileys Bridge (Node.js subprocess) for personal-phone QR-code pairing.

Mirrors TypeScript: openclaw/extensions/whatsapp/index.ts

Prerequisites:
  1. Node.js >=18 and npm must be installed.
  2. Run:  cd extensions/whatsapp/bridge && npm install
     (or:   cd extensions/whatsapp/bridge && npm install && npm run build)
  3. tsx must be available (installed globally or via npm).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def register(api) -> None:
    """Register WhatsApp channel with the openclaw plugin API."""
    try:
        from openclaw.channels.whatsapp import WhatsAppChannel

        channel = WhatsAppChannel()
        api.register_channel(channel)

        # Register agent tools (mirrors TS agentTools: () => [createLoginTool()])
        try:
            from openclaw.channels.whatsapp.tools.whatsapp_login import register as reg_login
            reg_login(api, channel)
        except Exception as tool_err:
            logger.warning("WhatsApp: failed to register login tool: %s", tool_err)

        logger.info("WhatsApp channel registered (Baileys bridge mode)")
    except ImportError as e:
        logger.warning(
            "WhatsApp channel unavailable — missing dependency: %s. "
            "Ensure openclaw-python is installed and bridge deps are set up: "
            "cd extensions/whatsapp/bridge && npm install",
            e,
        )


plugin = {
    "id": "whatsapp",
    "name": "WhatsApp",
    "description": (
        "WhatsApp personal-phone channel via Baileys bridge. "
        "Supports QR-code pairing, DM/group messaging, media, reactions, and polls."
    ),
    "register": register,
}
