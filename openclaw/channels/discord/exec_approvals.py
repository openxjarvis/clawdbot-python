"""
Exec approval DM forwarding.
Mirrors src/discord/monitor/exec-approvals.ts.

When execApprovals.enabled=True, tool execution requests are sent as DMs
to configured approvers with Allow Once / Always Allow / Deny buttons.
After resolution, buttons are disabled (the message is NOT deleted so
approvers can still read the decision context).
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)

# Default TTL before the request auto-expires (mirrors TS default)
_DEFAULT_TIMEOUT_SECS = 300.0  # 5 minutes


class ExecApprovalRequest:
    """Tracks a pending exec approval and its resolution future."""

    def __init__(
        self,
        request_id: str,
        description: str,
        approver_ids: list[str],
        on_resolve: Callable[[str, str], Awaitable[None]],
        expires_at: float | None = None,
    ) -> None:
        self.request_id = request_id
        self.description = description
        self.approver_ids = approver_ids
        self.on_resolve = on_resolve
        self.expires_at: float = expires_at if expires_at is not None else (
            time.time() + _DEFAULT_TIMEOUT_SECS
        )
        self.resolved = False
        self._sent_messages: list[Any] = []  # discord.Message objects


async def send_approval_request(
    client: Any,
    request: ExecApprovalRequest,
    target: str = "dm",
    channel: Any = None,
    cleanup_after_resolve: bool = False,
    accent_color: str | None = None,
) -> None:
    """
    Send an approval request to configured approvers.

    target:
      "dm"      — send to each approver via DM
      "channel" — send to the originating channel
      "both"    — send both DM and channel

    Note: cleanup_after_resolve is intentionally ignored in favour of keeping
    the message visible so approvers can read the decision context.  Buttons
    are disabled after resolution instead.
    """
    import discord

    # Build expiry timestamp for Discord's relative-time format <t:…:R>
    expires_at_unix = int(request.expires_at)
    footer_text = f"Expires <t:{expires_at_unix}:R> · ID: {request.request_id}"

    embed = discord.Embed(
        title="Execution Approval Request",
        description=request.description,
        color=_parse_color(accent_color) or discord.Color.orange(),
    )
    embed.set_footer(text=footer_text)

    view = _build_approval_view(request)

    sent: list[Any] = []

    if target in ("dm", "both"):
        for approver_id in request.approver_ids:
            try:
                user = await client.fetch_user(int(approver_id))
                dm = await user.create_dm()
                msg = await dm.send(embed=embed, view=view)
                sent.append(msg)
            except Exception as exc:
                logger.warning("[discord][approvals] Failed to DM approver %s: %s", approver_id, exc)

    if target in ("channel", "both") and channel:
        try:
            msg = await channel.send(embed=embed, view=view)
            sent.append(msg)
        except Exception as exc:
            logger.warning("[discord][approvals] Failed to send to channel: %s", exc)

    request._sent_messages = sent

    # Schedule auto-expiry
    timeout_secs = max(0.0, request.expires_at - time.time())
    asyncio.create_task(
        _auto_expire(request, timeout_secs),
        name=f"discord_exec_expire_{request.request_id}",
    )


async def _auto_expire(request: ExecApprovalRequest, timeout_secs: float) -> None:
    """Resolve the request as denied after timeout."""
    await asyncio.sleep(timeout_secs)
    if request.resolved:
        return
    request.resolved = True
    logger.info("[discord][approvals] Request %s expired", request.request_id)
    for msg in request._sent_messages:
        try:
            import discord
            expired_embed = discord.Embed(
                title="Execution Approval Request — Expired",
                description=request.description,
                color=discord.Color.greyple(),
            )
            expired_embed.set_footer(text=f"ID: {request.request_id} · Expired")
            await msg.edit(embed=expired_embed, view=None)
        except Exception:
            pass
    try:
        await request.on_resolve("deny", "system:expired")
    except Exception as exc:
        logger.debug("[discord][approvals] Error calling on_resolve for expired request: %s", exc)


def _build_approval_view(request: ExecApprovalRequest) -> Any:
    import discord

    view = discord.ui.View(timeout=None)  # timeout handled by _auto_expire
    approver_set = set(str(a) for a in request.approver_ids)

    allow_once_btn = discord.ui.Button(
        label="Allow Once",
        style=discord.ButtonStyle.success,
        custom_id=f"allow_once_{request.request_id}",
    )
    allow_always_btn = discord.ui.Button(
        label="Always Allow",
        style=discord.ButtonStyle.primary,
        custom_id=f"allow_always_{request.request_id}",
    )
    deny_btn = discord.ui.Button(
        label="Deny",
        style=discord.ButtonStyle.danger,
        custom_id=f"deny_{request.request_id}",
    )

    async def _handle(interaction: discord.Interaction, decision: str) -> None:
        user_id = str(interaction.user.id)
        if user_id not in approver_set:
            await interaction.response.send_message(
                "You are not authorized to approve this request.",
                ephemeral=True,
            )
            return

        if request.resolved:
            await interaction.response.send_message(
                "This request has already been resolved.",
                ephemeral=True,
            )
            return

        request.resolved = True
        label_map = {
            "allow-once": "Allowed (once)",
            "allow-always": "Always Allowed",
            "deny": "Denied",
        }
        label = label_map.get(decision, decision)

        await interaction.response.send_message(
            f"Request **{label}**.",
            ephemeral=True,
        )

        # Disable all buttons in the view and update embed
        for item in view.children:
            item.disabled = True  # type: ignore[attr-defined]
        try:
            if interaction.message:
                import discord as _d
                resolved_embed = _d.Embed(
                    title=f"Execution Approval — {label}",
                    description=request.description,
                    color=_d.Color.green() if "allow" in decision else _d.Color.red(),
                )
                resolved_embed.set_footer(
                    text=f"ID: {request.request_id} · Resolved by {interaction.user}"
                )
                await interaction.message.edit(embed=resolved_embed, view=view)
        except Exception:
            pass

        await request.on_resolve(decision, user_id)

    async def allow_once_callback(interaction: discord.Interaction) -> None:
        await _handle(interaction, "allow-once")

    async def allow_always_callback(interaction: discord.Interaction) -> None:
        await _handle(interaction, "allow-always")

    async def deny_callback(interaction: discord.Interaction) -> None:
        await _handle(interaction, "deny")

    allow_once_btn.callback = allow_once_callback
    allow_always_btn.callback = allow_always_callback
    deny_btn.callback = deny_callback
    view.add_item(allow_once_btn)
    view.add_item(allow_always_btn)
    view.add_item(deny_btn)
    return view


def _parse_color(color_str: str | None) -> int | None:
    if not color_str:
        return None
    try:
        return int(color_str.lstrip("#"), 16)
    except (ValueError, AttributeError):
        return None
