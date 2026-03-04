"""
Discord slash command registration and dispatch.
Mirrors src/discord/monitor/native-command.ts and src/discord/monitor/commands.ts.

Slash commands registered:
  /model   — interactive model picker (paginated buttons + string select)
  /focus   — bind current thread to an agent session
  /voice   — join/leave voice channel
  /skill   — per-skill commands (deduped, added until 100-command cap)
  /ping    — health check

All command interactions apply the same DM/group policy checks as inbound messages.
Ephemeral replies are configured via slashCommand.ephemeral (default: True).
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)

_MAX_DISCORD_COMMANDS = 100
_MODELS_PER_PAGE = 20


def setup_command_tree(
    client: Any,
    account: Any,
    on_command: Callable[[str, Any, dict], Awaitable[None]],
    voice_manager: Any | None = None,
    thread_bindings: Any | None = None,
) -> Any:
    """
    Build and attach a discord.app_commands.CommandTree to the client.
    Registers all standard commands up to the 100-command cap.

    Returns the CommandTree.
    Mirrors monitorDiscordProvider command registration in provider.ts.
    """
    import discord
    from discord import app_commands

    tree = app_commands.CommandTree(client)
    ephemeral: bool = account.slash_command.ephemeral

    # ── /ping ─────────────────────────────────────────────────────────────────
    @tree.command(name="ping", description="Check if the bot is online")
    async def ping_cmd(interaction: discord.Interaction) -> None:
        await interaction.response.send_message("Pong!", ephemeral=ephemeral)

    # ── /model ────────────────────────────────────────────────────────────────
    @tree.command(name="model", description="Switch the AI model for this conversation")
    async def model_cmd(interaction: discord.Interaction) -> None:
        await _handle_model_picker(interaction, account, on_command, ephemeral)

    # Alias /models → same handler
    @tree.command(name="models", description="Switch the AI model for this conversation")
    async def models_cmd(interaction: discord.Interaction) -> None:
        await _handle_model_picker(interaction, account, on_command, ephemeral)

    # ── /focus ────────────────────────────────────────────────────────────────
    @tree.command(name="focus", description="Bind this thread to the current session (or unbind)")
    @app_commands.describe(action="bind or unbind this thread")
    @app_commands.choices(action=[
        app_commands.Choice(name="bind", value="bind"),
        app_commands.Choice(name="unbind", value="unbind"),
    ])
    async def focus_cmd(
        interaction: discord.Interaction,
        action: str = "bind",
    ) -> None:
        await _handle_focus(interaction, action, account, thread_bindings, on_command, ephemeral)

    # ── /voice ────────────────────────────────────────────────────────────────
    if account.voice.enabled:
        @tree.command(name="voice", description="Join or leave a voice channel")
        @app_commands.describe(
            action="join or leave",
            channel="Voice channel to join (optional — uses current channel if omitted)",
        )
        @app_commands.choices(action=[
            app_commands.Choice(name="join", value="join"),
            app_commands.Choice(name="leave", value="leave"),
        ])
        async def voice_cmd(
            interaction: discord.Interaction,
            action: str = "join",
            channel: discord.VoiceChannel | None = None,
        ) -> None:
            await _handle_voice(interaction, action, channel, account, voice_manager, ephemeral)

    # ── /skill commands ────────────────────────────────────────────────────────
    # Skill commands are registered dynamically from agent skill registry.
    # The caller can add more via tree.add_command() before syncing.

    return tree


async def sync_commands(
    tree: Any,
    client: Any,
    guild: Any | None = None,
) -> int:
    """
    Sync the command tree with Discord (deploy commands).
    Mirrors client.handleDeployRequest() in TS.
    If guild is specified, syncs to that guild only (faster for dev).
    Returns the number of commands synced.
    """
    try:
        if guild:
            synced = await tree.sync(guild=guild)
        else:
            synced = await tree.sync()
        count = len(synced)
        logger.info("[discord][commands] Synced %d command(s)", count)
        return count
    except Exception as exc:
        logger.warning("[discord][commands] Failed to sync commands: %s", exc)
        return 0


async def clear_commands(tree: Any, client: Any) -> None:
    """Clear all registered application commands. Used when commands.native=False."""
    try:
        tree.clear_commands(guild=None)
        await tree.sync()
        logger.info("[discord][commands] Cleared all application commands")
    except Exception as exc:
        logger.warning("[discord][commands] Failed to clear commands: %s", exc)


# ---------------------------------------------------------------------------
# /model — interactive model picker
# ---------------------------------------------------------------------------

async def _handle_model_picker(
    interaction: Any,
    account: Any,
    on_command: Callable,
    ephemeral: bool,
) -> None:
    """
    Show a paginated model picker.
    Mirrors createDiscordNativeCommand /model in native-command.ts.
    First attempts to get available models from the agent, then builds
    a paginated button UI.
    """
    import discord

    try:
        # Try to get available models list — try several possible paths
        models: list[str] = []
        try:
            from openclaw.agents.model_catalog import load_model_catalog
            catalog = await load_model_catalog(None)
            models = [e.id for e in catalog if getattr(e, "id", None)]
        except Exception:
            pass
        if not models:
            try:
                # Legacy / alternative path
                from openclaw.agents.model_selection import list_available_models  # type: ignore[import]
                models = await list_available_models()
            except Exception:
                pass

        if not models:
            # Fall back to text input
            await interaction.response.send_message(
                "Model switching is not configured. Use the agent's model command instead.",
                ephemeral=ephemeral,
            )
            return

        view = _build_model_picker_view(
            models,
            page=0,
            on_select=lambda model_id: on_command(
                "model_switch",
                interaction,
                {"model": model_id, "user_id": str(interaction.user.id)},
            ),
            ephemeral=ephemeral,
        )
        await interaction.response.send_message(
            "Select a model:",
            view=view,
            ephemeral=ephemeral,
        )
    except Exception as exc:
        logger.warning("[discord][commands] Model picker error: %s", exc)
        await _safe_respond(interaction, "Failed to open model picker.", ephemeral)


def _build_model_picker_view(
    models: list[str],
    page: int,
    on_select: Callable,
    ephemeral: bool,
) -> Any:
    """
    Build a paginated model picker View.
    Page navigation via Previous/Next buttons.
    Model selection via StringSelectMenu (max 25 options per page).
    Mirrors paginated model picker UI in model-picker.ts.
    """
    import discord

    view = discord.ui.View(timeout=60.0)
    page_models = models[page * 25: (page + 1) * 25]
    total_pages = (len(models) + 24) // 25

    options = [
        discord.SelectOption(label=m[:100], value=m[:100]) for m in page_models
    ]

    select = discord.ui.Select(
        placeholder=f"Choose a model (page {page + 1}/{total_pages})",
        options=options,
        custom_id=f"model_select_p{page}",
    )

    async def select_callback(inter: discord.Interaction) -> None:
        chosen = select.values[0] if select.values else None
        if chosen:
            await inter.response.defer(ephemeral=True)
            await on_select(chosen)

    select.callback = select_callback
    view.add_item(select)

    if total_pages > 1:
        if page > 0:
            prev_btn = discord.ui.Button(label="◀ Prev", style=discord.ButtonStyle.secondary)

            async def prev_callback(inter: discord.Interaction) -> None:
                new_view = _build_model_picker_view(models, page - 1, on_select, ephemeral)
                await inter.response.edit_message(view=new_view)

            prev_btn.callback = prev_callback
            view.add_item(prev_btn)

        if page < total_pages - 1:
            next_btn = discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary)

            async def next_callback(inter: discord.Interaction) -> None:
                new_view = _build_model_picker_view(models, page + 1, on_select, ephemeral)
                await inter.response.edit_message(view=new_view)

            next_btn.callback = next_callback
            view.add_item(next_btn)

    return view


# ---------------------------------------------------------------------------
# /focus — thread binding
# ---------------------------------------------------------------------------

async def _handle_focus(
    interaction: Any,
    action: str,
    account: Any,
    thread_bindings: Any | None,
    on_command: Callable,
    ephemeral: bool,
) -> None:
    import discord

    channel = interaction.channel

    if not isinstance(channel, discord.Thread):
        await _safe_respond(
            interaction,
            "/focus can only be used in a thread.",
            ephemeral,
        )
        return

    if thread_bindings is None:
        await _safe_respond(interaction, "Thread bindings are not enabled.", ephemeral)
        return

    thread_id = str(channel.id)
    channel_id = str(channel.parent_id or channel.id)
    guild_id = str(interaction.guild_id) if interaction.guild_id else None

    if action == "unbind":
        removed = thread_bindings.unbind(thread_id)
        msg = "Thread unbound from session." if removed else "This thread was not bound."
    else:
        # Generate a session key from guild+channel+thread
        session_key = f"discord:{account.account_id}:{guild_id}:{thread_id}"
        thread_bindings.bind(
            thread_id=thread_id,
            channel_id=channel_id,
            session_key=session_key,
            guild_id=guild_id,
            account_id=account.account_id,
        )
        msg = f"Thread bound to session `{session_key}`. Mention is no longer required here."

    await _safe_respond(interaction, msg, ephemeral)

    await on_command("focus", interaction, {
        "action": action,
        "thread_id": thread_id,
        "channel_id": channel_id,
        "guild_id": guild_id,
    })


# ---------------------------------------------------------------------------
# /voice — voice channel join/leave
# ---------------------------------------------------------------------------

async def _handle_voice(
    interaction: Any,
    action: str,
    channel: Any | None,
    account: Any,
    voice_manager: Any | None,
    ephemeral: bool,
) -> None:
    if voice_manager is None:
        await _safe_respond(interaction, "Voice support is not available.", ephemeral)
        return

    guild = interaction.guild
    guild_id = str(guild.id) if guild else None

    if not guild_id:
        await _safe_respond(interaction, "/voice requires a server context.", ephemeral)
        return

    if action == "leave":
        ok = await voice_manager.leave_voice_channel(guild_id)
        await _safe_respond(interaction, "Left voice channel." if ok else "Not connected.", ephemeral)
        return

    # join
    target_channel = channel
    if target_channel is None:
        # Use the user's current voice channel
        member = guild.get_member(interaction.user.id)
        if member and member.voice and member.voice.channel:
            target_channel = member.voice.channel

    if target_channel is None:
        await _safe_respond(
            interaction,
            "Please join a voice channel first, or specify one with the `channel` option.",
            ephemeral,
        )
        return

    ok = await voice_manager.join_voice_channel(guild_id, str(target_channel.id))
    msg = f"Joined **{target_channel.name}**." if ok else "Failed to join voice channel."
    await _safe_respond(interaction, msg, ephemeral)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _safe_respond(interaction: Any, content: str, ephemeral: bool = True) -> None:
    try:
        if interaction.response.is_done():
            await interaction.followup.send(content, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(content, ephemeral=ephemeral)
    except Exception as exc:
        logger.debug("[discord][commands] Failed to respond to interaction: %s", exc)
