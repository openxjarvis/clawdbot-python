"""Thread ownership extension — tracks @-mention-based thread ownership.

Mirrors TypeScript: openclaw/extensions/thread-ownership/index.ts

Intercepts message_received hook to track which threads this agent has been
@-mentioned in (TTL: 5 minutes), and overrides the target agent for subsequent
messages in those threads.
"""
from __future__ import annotations

import time

_MENTION_TTL_MS = 5 * 60 * 1000
_mentioned_threads: dict[str, int] = {}


def _clean_expired_mentions() -> None:
    now_ms = int(time.time() * 1000)
    expired = [k for k, ts in _mentioned_threads.items() if now_ms - ts > _MENTION_TTL_MS]
    for k in expired:
        del _mentioned_threads[k]


def register(api) -> None:
    async def on_message(event: dict, context: dict) -> None:
        _clean_expired_mentions()
        # TODO: implement mention tracking and thread-ownership forwarding logic
        # See openclaw/extensions/thread-ownership/index.ts for reference

    # PluginApi.on() requires handler as positional argument (no decorator syntax)
    api.on("message_received", on_message)

plugin = {
    "id": "thread-ownership",
    "name": "Thread Ownership",
    "description": "Prevents multiple agents from responding in the same Slack thread.",
    "register": register,
}
