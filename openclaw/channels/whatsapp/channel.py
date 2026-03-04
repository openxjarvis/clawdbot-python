"""WhatsAppChannel — main channel plugin class.

Integrates all WhatsApp sub-modules and implements the ChannelPlugin interface.
Uses the Baileys Bridge (Node.js subprocess) for the personal-phone QR path.

Mirrors TypeScript: extensions/whatsapp/src/channel.ts
"""
from __future__ import annotations

import logging
from typing import Any

from ..base import ChannelCapabilities, ChannelPlugin, InboundMessage

logger = logging.getLogger(__name__)


class WhatsAppChannel(ChannelPlugin):
    """
    WhatsApp channel for openclaw-python.

    Supports:
      - Personal-phone QR-code pairing via Baileys bridge (subprocess)
      - DM + group messaging
      - Multi-account configuration
      - Media (images, video, audio, documents) with size optimization
      - Emoji reactions (ack reaction + agent reactions)
      - Native polls (up to 12 options)
      - Markdown → WhatsApp format conversion
      - DM pairing policy, group allowlist, group mention gating
      - Message deduplication (memory + persistent)
      - Configurable debouncing
      - Read receipts (blue ticks)
      - Text chunking (configurable length/newline mode)

    Configuration (channels.whatsapp in openclaw.json):
      dmPolicy, allowFrom, groupPolicy, groupAllowFrom, groups,
      debounceMs, ackReaction, textChunkLimit, chunkMode, mediaMaxMb,
      sendReadReceipts, selfChatMode, blockStreaming, ...
    """

    def __init__(self) -> None:
        super().__init__()
        self.id = "whatsapp"
        self.label = "WhatsApp"
        self.capabilities = ChannelCapabilities(
            chat_types=["direct", "group"],
            supports_media=True,
            supports_reactions=True,
            supports_threads=False,
            supports_polls=True,
            supports_edit=False,
            supports_reply=True,
            block_streaming=True,  # WhatsApp only receives final replies
        )

        from .monitor import WhatsAppMonitor
        from .config import ResolvedWhatsAppAccount
        from .outbound import WhatsAppOutboundAdapter

        self._monitor: WhatsAppMonitor = WhatsAppMonitor()
        self._accounts: list[ResolvedWhatsAppAccount] = []
        self._default_outbound: WhatsAppOutboundAdapter | None = None
        self._outbound_by_account: dict[str, WhatsAppOutboundAdapter] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def on_start(self, config: dict[str, Any]) -> None:
        """Start the Baileys bridge and account monitors."""
        from .config import parse_whatsapp_config
        from .outbound import WhatsAppOutboundAdapter

        self._accounts = parse_whatsapp_config(config)
        if not self._accounts:
            logger.warning(
                "[whatsapp] No valid accounts configured. "
                "Set channels.whatsapp.dmPolicy or accounts map."
            )
            return

        if not self._message_handler:
            raise RuntimeError("WhatsAppChannel: message handler not set before start()")

        async def dispatch(msg: InboundMessage) -> None:
            await self._handle_message(msg)

        bridge_client = await self._monitor.start(self._accounts, dispatch)

        # Build per-account outbound adapters
        for account in self._accounts:
            adapter = WhatsAppOutboundAdapter(bridge_client, account)
            self._outbound_by_account[account.account_id] = adapter

        if self._accounts:
            default_account = self._accounts[0]
            self._default_outbound = self._outbound_by_account.get(default_account.account_id)

        logger.info(
            "[whatsapp] Channel started with %d account(s): %s",
            len(self._accounts),
            [a.account_id for a in self._accounts],
        )

    async def on_stop(self) -> None:
        """Stop the bridge and all account sessions."""
        await self._monitor.stop()
        self._default_outbound = None
        self._outbound_by_account.clear()
        logger.info("[whatsapp] Channel stopped")

    # ------------------------------------------------------------------
    # Outbound (required abstract implementation)
    # ------------------------------------------------------------------

    async def send_text(
        self,
        target: str,
        text: str,
        reply_to: str | None = None,
    ) -> str:
        """Send a text message to target (E.164 number or JID)."""
        outbound = self._get_outbound(target)
        result = await outbound.send_text(target, text, reply_to)
        await self._track_send()
        return result

    async def send_media(
        self,
        target: str,
        media_url: str,
        media_type: str,
        caption: str | None = None,
    ) -> str:
        """Send a media message to target."""
        outbound = self._get_outbound(target)
        result = await outbound.send_media(target, media_url, media_type, caption)
        await self._track_send()
        return result

    async def send_reaction(
        self,
        target: str,
        message_id: str,
        emoji: str,
        remove: bool = False,
    ) -> None:
        """Send or remove an emoji reaction."""
        outbound = self._get_outbound(target)
        await outbound.send_reaction(target, message_id, emoji, remove)

    async def send_poll(
        self,
        target: str,
        question: str,
        options: list[str],
        max_selections: int = 1,
    ) -> str:
        """Send a native WhatsApp poll."""
        outbound = self._get_outbound(target)
        return await outbound.send_poll(target, question, options, max_selections)

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def check_health(self) -> tuple[bool, str]:
        if not self._running:
            return False, "Channel not running"
        if not self._monitor.is_running:
            return False, "Monitor not running"
        client = self._monitor.bridge_client
        if client is None:
            return False, "Bridge client not initialized"
        bridge_ok = await client.health_check()
        if not bridge_ok:
            return False, "Bridge unreachable"
        return True, "OK"

    # ------------------------------------------------------------------
    # QR login helpers (mirrors TS loginWithQrStart / loginWithQrWait)
    # ------------------------------------------------------------------

    async def get_qr(self, account_id: str = "default") -> dict[str, Any]:
        """
        Get QR code data URL for the specified account.
        Returns {"qr": "<png-data-url>"} or {"status": "pending"} if not yet available.
        """
        client = self._monitor.bridge_client
        if client is None:
            return {"error": "Bridge not started"}
        return await client.get_qr(account_id)

    async def get_session_status(self, account_id: str = "default") -> dict[str, Any]:
        """Return current session state for the account."""
        client = self._monitor.bridge_client
        if client is None:
            return {"state": "not_started"}
        try:
            return await client.get_status(account_id)
        except Exception as e:
            return {"state": "error", "error": str(e)}

    async def logout(self, account_id: str = "default") -> None:
        """Logout a session and clear its credentials."""
        client = self._monitor.bridge_client
        if client:
            await client.logout(account_id)

    # ------------------------------------------------------------------
    # Agent tools
    # ------------------------------------------------------------------

    def agent_tools(self) -> list[dict]:
        """Return agent tool descriptors for this channel.

        Mirrors TS: agentTools: () => [createLoginTool()]
        """
        return [
            {
                "name": "whatsapp_login",
                "description": (
                    "Generate a WhatsApp QR code for linking, or wait for the scan to complete."
                ),
                "owner_only": True,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["start", "wait"],
                        },
                        "account_id": {"type": "string"},
                        "timeout_ms": {"type": "number"},
                        "force": {"type": "boolean"},
                    },
                    "required": ["action"],
                },
                "execute": self._execute_login_tool,
            }
        ]

    async def _execute_login_tool(self, tool_call_id: str, args: dict) -> dict:
        from .tools.whatsapp_login import run_whatsapp_login
        return await run_whatsapp_login(args, self)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_outbound(self, target: str) -> "WhatsAppOutboundAdapter":  # type: ignore
        """Select the correct outbound adapter for *target*.

        Mirrors TypeScript resolveWhatsAppOutboundTarget: for each account,
        check whether the target normalizes to an entry in that account's
        allowFrom list; fall back to the default account.
        """
        if not self._outbound_by_account:
            raise RuntimeError(
                "WhatsAppChannel: no outbound adapter available (channel not started?)"
            )

        # Single-account fast path
        if len(self._outbound_by_account) == 1:
            return next(iter(self._outbound_by_account.values()))

        # Multi-account: find the account whose allowFrom matches target
        normalized_target = self._normalize_target(target)
        for account in self._accounts:
            allow_from = getattr(account, "allow_from", None) or []
            normalized_allow = [self._normalize_target(str(e)) for e in allow_from]
            if "*" in normalized_allow:
                # Wildcard — this account accepts anything; check if it's the first match
                pass
            elif normalized_target and normalized_target in normalized_allow:
                adapter = self._outbound_by_account.get(account.account_id)
                if adapter:
                    return adapter

        # Fall back to default account
        if self._default_outbound is None:
            raise RuntimeError("WhatsAppChannel: no default outbound adapter")
        return self._default_outbound

    @staticmethod
    def _normalize_target(target: str) -> str:
        """Normalize a phone number or JID for comparison."""
        t = target.strip()
        # Strip @s.whatsapp.net suffix if present
        if "@" in t:
            t = t.split("@")[0]
        # Remove leading +
        if t.startswith("+"):
            t = t[1:]
        return t

    def get_outbound_for_account(self, account_id: str) -> "WhatsAppOutboundAdapter | None":  # type: ignore
        return self._outbound_by_account.get(account_id)
