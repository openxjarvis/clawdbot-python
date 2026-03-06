"""
Agent-controlled interactive Discord components.
Mirrors src/discord/monitor/agent-components.ts and src/discord/components.ts.

Supports:
  - Buttons (primary, secondary, success, danger, link)
  - String/User/Role/Channel/Mentionable select menus
  - Modals (text input forms)

When the agent includes component specs in its reply, this module builds
discord.ui.View objects, registers them in a central registry keyed by
custom_id, and routes interaction callbacks back to the agent as new
InboundMessage events (with type="component_interaction").
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)

_COMPONENT_TTL = 900.0  # 15 minutes — discard stale views


# ---------------------------------------------------------------------------
# Component registry — routes interaction → agent callback
# ---------------------------------------------------------------------------

class _ComponentRegistry:
    def __init__(self) -> None:
        self._callbacks: dict[str, tuple[Callable, float]] = {}

    def register(self, custom_id: str, callback: Callable[..., Awaitable]) -> None:
        self._callbacks[custom_id] = (callback, time.monotonic() + _COMPONENT_TTL)
        self._evict()

    def pop(self, custom_id: str) -> Callable | None:
        entry = self._callbacks.pop(custom_id, None)
        return entry[0] if entry else None

    def _evict(self) -> None:
        now = time.monotonic()
        stale = [k for k, (_, exp) in self._callbacks.items() if now > exp]
        for k in stale:
            del self._callbacks[k]


_registry = _ComponentRegistry()


# ---------------------------------------------------------------------------
# View builder
# ---------------------------------------------------------------------------

def _make_custom_id(prefix: str = "cmp") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def build_view_from_spec(
    spec: dict[str, Any],
    on_interaction: Callable[..., Awaitable],
    accent_color: str | None = None,
    timeout: float = 600.0,
) -> Any:
    """
    Build a discord.ui.View from an agent-provided component spec.

    Spec format (mirrors TS agent-components.ts):
    {
      "components": [
        {
          "type": "button",
          "label": "Approve",
          "style": "success",   # primary/secondary/success/danger/link
          "custom_id": "approve_123",  # optional; auto-generated if absent
          "url": "https://..."  # for link buttons
        },
        {
          "type": "select",
          "placeholder": "Choose an option",
          "options": [
            {"label": "Option A", "value": "a"},
            {"label": "Option B", "value": "b"}
          ]
        },
        {
          "type": "modal_trigger",
          "label": "Open form",
          "style": "primary",
          "modal": {
            "title": "My Form",
            "fields": [
              {"label": "Name", "placeholder": "Enter your name", "required": true}
            ]
          }
        }
      ]
    }
    """
    import discord

    view = discord.ui.View(timeout=timeout)
    component_specs = spec.get("components") or []

    for comp in component_specs:
        comp_type = (comp.get("type") or "button").lower()

        if comp_type == "button":
            _add_button(view, comp, on_interaction)
        elif comp_type in ("select", "string_select"):
            _add_string_select(view, comp, on_interaction)
        elif comp_type == "user_select":
            _add_user_select(view, comp, on_interaction)
        elif comp_type == "role_select":
            _add_role_select(view, comp, on_interaction)
        elif comp_type == "channel_select":
            _add_channel_select(view, comp, on_interaction)
        elif comp_type == "modal_trigger":
            _add_modal_trigger(view, comp, on_interaction)

    return view


# ---------------------------------------------------------------------------
# Individual component builders
# ---------------------------------------------------------------------------

_BUTTON_STYLE_MAP = {
    "primary": None,
    "secondary": None,
    "success": None,
    "danger": None,
    "link": None,
}


def _resolve_button_style(style_str: str | None) -> Any:
    import discord
    mapping = {
        "primary": discord.ButtonStyle.primary,
        "secondary": discord.ButtonStyle.secondary,
        "success": discord.ButtonStyle.success,
        "danger": discord.ButtonStyle.danger,
        "link": discord.ButtonStyle.link,
    }
    return mapping.get(style_str or "primary", discord.ButtonStyle.primary)


def _add_button(view: Any, spec: dict[str, Any], on_interaction: Callable) -> None:
    import discord

    custom_id = spec.get("custom_id") or _make_custom_id("btn")
    label = spec.get("label") or "Click"
    style = _resolve_button_style(spec.get("style"))
    url = spec.get("url")
    emoji = spec.get("emoji")

    if url:
        btn = discord.ui.Button(label=label, url=url, emoji=emoji)
    else:
        btn = discord.ui.Button(
            label=label,
            style=style,
            custom_id=custom_id,
            emoji=emoji,
        )

        async def callback(interaction: discord.Interaction) -> None:
            await interaction.response.defer(ephemeral=True)
            payload = {
                "type": "button",
                "custom_id": custom_id,
                "label": label,
                "user_id": str(interaction.user.id),
                "user_name": interaction.user.display_name,
                "channel_id": str(interaction.channel_id),
                "message_id": str(interaction.message.id) if interaction.message else None,
            }
            await on_interaction(interaction, payload)

        btn.callback = callback
        _registry.register(custom_id, lambda i, p: on_interaction(i, p))

    view.add_item(btn)


def _add_string_select(view: Any, spec: dict[str, Any], on_interaction: Callable) -> None:
    import discord

    custom_id = spec.get("custom_id") or _make_custom_id("sel")
    placeholder = spec.get("placeholder") or "Select an option"
    options_raw = spec.get("options") or []
    min_values = int(spec.get("min_values") or 1)
    max_values = int(spec.get("max_values") or 1)

    options = [
        discord.SelectOption(
            label=str(o.get("label", "Option")),
            value=str(o.get("value", o.get("label", ""))),
            description=o.get("description"),
            emoji=o.get("emoji"),
        )
        for o in options_raw[:25]  # Discord limit
    ]

    select = discord.ui.Select(
        custom_id=custom_id,
        placeholder=placeholder,
        options=options,
        min_values=min_values,
        max_values=min(max_values, len(options)),
    )

    async def callback(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        payload = {
            "type": "select",
            "custom_id": custom_id,
            "values": select.values,
            "user_id": str(interaction.user.id),
            "user_name": interaction.user.display_name,
            "channel_id": str(interaction.channel_id),
        }
        await on_interaction(interaction, payload)

    select.callback = callback
    view.add_item(select)


def _add_user_select(view: Any, spec: dict[str, Any], on_interaction: Callable) -> None:
    import discord

    custom_id = spec.get("custom_id") or _make_custom_id("usel")
    placeholder = spec.get("placeholder") or "Select users"

    select = discord.ui.UserSelect(custom_id=custom_id, placeholder=placeholder)

    async def callback(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        payload = {
            "type": "user_select",
            "custom_id": custom_id,
            "values": [str(u.id) for u in select.values],
            "user_id": str(interaction.user.id),
            "channel_id": str(interaction.channel_id),
        }
        await on_interaction(interaction, payload)

    select.callback = callback
    view.add_item(select)


def _add_role_select(view: Any, spec: dict[str, Any], on_interaction: Callable) -> None:
    import discord

    custom_id = spec.get("custom_id") or _make_custom_id("rsel")
    placeholder = spec.get("placeholder") or "Select roles"

    select = discord.ui.RoleSelect(custom_id=custom_id, placeholder=placeholder)

    async def callback(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        payload = {
            "type": "role_select",
            "custom_id": custom_id,
            "values": [str(r.id) for r in select.values],
            "user_id": str(interaction.user.id),
            "channel_id": str(interaction.channel_id),
        }
        await on_interaction(interaction, payload)

    select.callback = callback
    view.add_item(select)


def _add_channel_select(view: Any, spec: dict[str, Any], on_interaction: Callable) -> None:
    import discord

    custom_id = spec.get("custom_id") or _make_custom_id("csel")
    placeholder = spec.get("placeholder") or "Select channels"

    select = discord.ui.ChannelSelect(custom_id=custom_id, placeholder=placeholder)

    async def callback(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        payload = {
            "type": "channel_select",
            "custom_id": custom_id,
            "values": [str(c.id) for c in select.values],
            "user_id": str(interaction.user.id),
            "channel_id": str(interaction.channel_id),
        }
        await on_interaction(interaction, payload)

    select.callback = callback
    view.add_item(select)


def build_discord_buttons_view(
    buttons: list[list[dict]],
    on_click: Callable[..., Awaitable],
    timeout: float = 1800.0,
) -> Any:
    """
    Build a discord.ui.View from the [[buttons:...]] directive format.

    buttons: 2D list from parse_inline_directives(), each dict has:
      - "text": display label
      - "callback_data": string dispatched to agent on click

    Mirrors TS: src/discord/components.ts createButtonComponent()
    Used by DiscordChannel.send_text(buttons=...) to attach interactive
    buttons to the agent's reply.

    TTL is 30 minutes (1800s) to match TS component registry TTL.
    """
    import discord

    view = discord.ui.View(timeout=timeout)

    for row in buttons:
        for btn_spec in row:
            label = str(btn_spec.get("text", ""))
            if not label:
                continue
            callback_data = str(
                btn_spec.get("callback_data", btn_spec.get("text", ""))
            )
            style_key = btn_spec.get("style", "primary")
            style = _resolve_button_style(style_key)
            custom_id = _make_custom_id("btn")

            btn = discord.ui.Button(
                label=label[:80],
                style=style,
                custom_id=custom_id,
            )

            # Capture loop variables in the closure
            _label = label
            _callback_data = callback_data
            _custom_id = custom_id

            async def callback(
                interaction: discord.Interaction,
                _cd: str = _callback_data,
                _lbl: str = _label,
                _cid: str = _custom_id,
            ) -> None:
                try:
                    await interaction.response.defer(ephemeral=True)
                except Exception:
                    pass
                ctx = {
                    "type": "button",
                    "custom_id": _cid,
                    "label": _lbl,
                    "callback_data": _cd,
                    "user_id": str(interaction.user.id) if interaction.user else "",
                    "user_name": getattr(interaction.user, "display_name", "") if interaction.user else "",
                    "channel_id": str(interaction.channel_id) if interaction.channel_id else "",
                    "message_id": str(interaction.message.id) if interaction.message else "",
                    "guild_id": str(interaction.guild_id) if interaction.guild_id else None,
                }
                await on_click(_cd, ctx)

            btn.callback = callback  # type: ignore[method-assign]
            _registry.register(custom_id, lambda i, p, cd=callback_data, lbl=label: None)
            view.add_item(btn)

    return view


def _add_modal_trigger(view: Any, spec: dict[str, Any], on_interaction: Callable) -> None:
    """
    Add a button that opens a Modal when clicked.
    Modal submission is routed back to on_interaction as a new event.
    """
    import discord

    btn_label = spec.get("label") or "Open Form"
    btn_style = _resolve_button_style(spec.get("style"))
    modal_spec = spec.get("modal") or {}
    modal_title = str(modal_spec.get("title") or "Form")[:45]
    fields_raw = modal_spec.get("fields") or []
    btn_custom_id = spec.get("custom_id") or _make_custom_id("mtrig")

    # Build text inputs for the modal fields
    text_inputs: list[discord.ui.TextInput] = []
    for f in fields_raw[:5]:  # Discord allows max 5 components in a modal
        ti = discord.ui.TextInput(
            label=str(f.get("label") or "Input")[:45],
            placeholder=f.get("placeholder"),
            required=bool(f.get("required", True)),
            style=discord.TextStyle.long if f.get("multiline") else discord.TextStyle.short,
            custom_id=f.get("custom_id") or _make_custom_id("ti"),
        )
        text_inputs.append(ti)

    # Capture text_inputs in closure for modal class (public API, no private attrs)
    _ti_snapshot = list(text_inputs)
    _modal_title = modal_title

    class _AgentModal(discord.ui.Modal, title=_modal_title):
        async def on_submit(self, interaction: discord.Interaction) -> None:
            await interaction.response.defer(ephemeral=True)
            payload = {
                "type": "modal_submit",
                "modal_title": _modal_title,
                "values": {ti.custom_id: ti.value for ti in _ti_snapshot},
                "user_id": str(interaction.user.id),
                "user_name": interaction.user.display_name,
                "channel_id": str(interaction.channel_id),
            }
            await on_interaction(interaction, payload)

    # Add text inputs to the modal using the public add_item() method
    for ti in _ti_snapshot:
        _AgentModal.add_item(ti)  # type: ignore[arg-type]

    btn = discord.ui.Button(label=btn_label, style=btn_style, custom_id=btn_custom_id)

    async def btn_callback(interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(_AgentModal())

    btn.callback = btn_callback
    view.add_item(btn)
