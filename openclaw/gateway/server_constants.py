"""
Gateway server constants — fully aligned with TypeScript
openclaw/src/gateway/server-constants.ts.

Keep client-side WS limits aligned with server maxPayload so large
canvas snapshots don't get disconnected mid-invoke.
"""
from __future__ import annotations

import os

# Keep server maxPayload aligned with gateway client maxPayload.
MAX_PAYLOAD_BYTES = 25 * 1024 * 1024  # 25 MB

# Per-connection send buffer limit (2x max payload).
MAX_BUFFERED_BYTES = 50 * 1024 * 1024  # 50 MB

# Keep history responses comfortably under client WS limits.
DEFAULT_MAX_CHAT_HISTORY_MESSAGES_BYTES = 6 * 1024 * 1024  # 6 MB

_max_chat_history_messages_bytes = DEFAULT_MAX_CHAT_HISTORY_MESSAGES_BYTES


def get_max_chat_history_messages_bytes() -> int:
    """Return the current max chat-history payload size (bytes)."""
    return _max_chat_history_messages_bytes


def _set_max_chat_history_messages_bytes_for_test(value: int | None = None) -> None:
    """Override the chat-history byte limit in test environments."""
    global _max_chat_history_messages_bytes
    is_test = os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("NODE_ENV") == "test"
    if not is_test:
        return
    if value is None:
        _max_chat_history_messages_bytes = DEFAULT_MAX_CHAT_HISTORY_MESSAGES_BYTES
        return
    if isinstance(value, int) and value > 0:
        _max_chat_history_messages_bytes = value


DEFAULT_HANDSHAKE_TIMEOUT_MS = 10_000


def get_handshake_timeout_ms() -> int:
    """Return the WebSocket handshake timeout in milliseconds."""
    env_val = os.environ.get("OPENCLAW_TEST_HANDSHAKE_TIMEOUT_MS")
    if env_val and os.environ.get("PYTEST_CURRENT_TEST"):
        try:
            parsed = int(env_val)
            if parsed > 0:
                return parsed
        except ValueError:
            pass
    return DEFAULT_HANDSHAKE_TIMEOUT_MS


TICK_INTERVAL_MS = 30_000          # Gateway tick / heartbeat interval
HEALTH_REFRESH_INTERVAL_MS = 60_000  # Health status refresh interval
DEDUPE_TTL_MS = 5 * 60_000         # 5 minutes (matches TS)
DEDUPE_MAX = 1_000                  # Max dedupe cache entries
