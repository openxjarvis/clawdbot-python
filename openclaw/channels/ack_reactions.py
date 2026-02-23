"""ACK reaction gating — mirrors src/channels/ack-reactions.ts"""
from __future__ import annotations

from typing import Awaitable, Callable, Literal

AckReactionScope = Literal["all", "direct", "group-all", "group-mentions", "off", "none"]
WhatsAppAckReactionMode = Literal["always", "mentions", "never"]


def should_ack_reaction(
    *,
    scope: AckReactionScope | None,
    is_direct: bool,
    is_group: bool,
    is_mentionable_group: bool,
    require_mention: bool,
    can_detect_mention: bool,
    effective_was_mentioned: bool,
    should_bypass_mention: bool = False,
) -> bool:
    effective_scope = scope or "group-mentions"

    if effective_scope in ("off", "none"):
        return False
    if effective_scope == "all":
        return True
    if effective_scope == "direct":
        return is_direct
    if effective_scope == "group-all":
        return is_group
    if effective_scope == "group-mentions":
        if not is_mentionable_group:
            return False
        if not require_mention:
            return False
        if not can_detect_mention:
            return False
        return effective_was_mentioned or should_bypass_mention
    return False


def should_ack_reaction_for_whatsapp(
    *,
    emoji: str,
    is_direct: bool,
    is_group: bool,
    direct_enabled: bool,
    group_mode: WhatsAppAckReactionMode,
    was_mentioned: bool,
    group_activated: bool,
) -> bool:
    if not emoji:
        return False
    if is_direct:
        return direct_enabled
    if not is_group:
        return False
    if group_mode == "never":
        return False
    if group_mode == "always":
        return True
    return should_ack_reaction(
        scope="group-mentions",
        is_direct=False,
        is_group=True,
        is_mentionable_group=True,
        require_mention=True,
        can_detect_mention=True,
        effective_was_mentioned=was_mentioned,
        should_bypass_mention=group_activated,
    )


def remove_ack_reaction_after_reply(
    *,
    remove_after_reply: bool,
    ack_reaction_value: str | None,
    ack_reaction_coro: Awaitable[bool] | None,
    remove: Callable[[], Awaitable[None]],
    on_error: Callable[[Exception], None] | None = None,
) -> None:
    """Schedule async removal of an ack reaction after the reply is sent.

    Callers are responsible for actually awaiting the coroutine in an event loop.
    Returns None; wraps logic to be called inside an async context with asyncio.create_task.
    """
    import asyncio

    if not remove_after_reply:
        return
    if ack_reaction_coro is None:
        return
    if not ack_reaction_value:
        return

    async def _do() -> None:
        try:
            did_ack = await ack_reaction_coro  # type: ignore[misc]
        except Exception:
            return
        if not did_ack:
            return
        try:
            await remove()
        except Exception as err:
            if on_error:
                on_error(err)

    asyncio.ensure_future(_do())
