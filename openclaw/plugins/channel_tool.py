"""ChannelHandlerTool — wraps channel-specific tool handlers as AgentTools.

Channel plugins (feishu, telegram, discord) register tools using the pattern:
    handler(params, client) -> dict

where `client` is a channel-specific API client (e.g. lark_oapi Client).

ChannelHandlerTool resolves the `client` at call time from the global
ChannelRegistry, making these tools available to the agent without requiring
the client to be available at registration time.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Channels that expose a Feishu lark_oapi client via ._default_outbound._client
_FEISHU_CHANNEL_IDS = {"feishu", "lark"}


class ChannelHandlerTool:
    """
    AgentTool-compatible wrapper for channel handler functions.

    The handler signature is:
        async handler(params: dict, client: Any) -> dict

    The `client` argument is resolved lazily from the channel registry at
    call time, so the channel does not need to be started at registration time.
    """

    def __init__(
        self,
        tool_name: str,
        description: str,
        schema: dict[str, Any],
        handler: Callable,
    ) -> None:
        self.name = tool_name
        self.description = description
        self._schema = schema
        self._handler = handler

    # ------------------------------------------------------------------
    # AgentTool interface
    # ------------------------------------------------------------------

    @property
    def parameters(self) -> dict[str, Any]:
        return self._schema

    def get_schema(self) -> dict[str, Any]:
        return self._schema

    async def execute(
        self,
        tool_call_id: str,
        params: dict[str, Any],
        signal: Any = None,
        ctx: Any = None,
    ) -> Any:
        """Execute the handler, injecting the channel client."""
        client = self._resolve_client(ctx)
        try:
            result = self._handler(params, client)
            if asyncio.iscoroutine(result):
                result = await result
            return result
        except Exception as exc:
            logger.warning("[channel_tool] %s error: %s", self.name, exc)
            return {"error": str(exc)}

    # ------------------------------------------------------------------
    # Client resolution
    # ------------------------------------------------------------------

    def _resolve_client(self, ctx: Any) -> Any:
        """
        Attempt to resolve the channel client from the runtime context.

        For Feishu tools, extracts _default_outbound._client from the
        FeishuChannel instance registered in the ChannelRegistry.
        """
        # Try to get channel_registry from ctx (ReplyContext or similar)
        channel_registry = getattr(ctx, "channel_registry", None)
        if channel_registry is None:
            # Fall back to global singleton if available
            channel_registry = _get_global_channel_registry()

        if channel_registry is None:
            logger.debug("[channel_tool] No channel_registry — calling handler without client")
            return None

        # Determine which channel owns this tool by name prefix
        for ch_id in _FEISHU_CHANNEL_IDS:
            channel = _get_channel(channel_registry, ch_id)
            if channel is not None:
                outbound = getattr(channel, "_default_outbound", None)
                if outbound is not None:
                    client = getattr(outbound, "_client", None)
                    if client is not None:
                        return client

        logger.debug("[channel_tool] Could not resolve client for tool %s", self.name)
        return None


# ---------------------------------------------------------------------------
# Global channel registry singleton reference
# ---------------------------------------------------------------------------

_global_channel_registry: Any = None


def set_global_channel_registry(registry: Any) -> None:
    """Called by bootstrap once the channel registry is initialized."""
    global _global_channel_registry
    _global_channel_registry = registry


def _get_global_channel_registry() -> Any:
    return _global_channel_registry


def _get_channel(registry: Any, channel_id: str) -> Any:
    """Get a channel from the registry by id."""
    if hasattr(registry, "get_channel"):
        return registry.get_channel(channel_id)
    if hasattr(registry, "channels"):
        channels = registry.channels
        if isinstance(channels, dict):
            return channels.get(channel_id)
        for ch in channels:
            if getattr(ch, "id", None) == channel_id:
                return ch
    return None
