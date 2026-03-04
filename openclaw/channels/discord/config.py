"""Discord channel config schema — mirrors src/config/types.discord.ts"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Literal

DmPolicy = Literal["open", "allowlist", "pairing", "disabled"]
GroupPolicy = Literal["open", "allowlist", "disabled"]
ReactionNotifications = Literal["off", "own", "all", "allowlist"]
StreamingMode = Literal["off", "partial", "block", "progress"]
ReplyToMode = Literal["off", "first", "all"]
AckReactionScope = Literal["group-mentions", "group-all", "direct", "all", "off", "none"]
ExecApprovalTarget = Literal["dm", "channel", "both"]
# Discord activity types: 0=Game,1=Streaming,2=Listening,3=Watching,4=Custom,5=Competing
ActivityType = Literal[0, 1, 2, 3, 4, 5]


@dataclass
class DiscordDmConfig:
    enabled: bool = True
    policy: DmPolicy = "pairing"
    allow_from: list[str] = field(default_factory=list)
    group_enabled: bool = False
    group_channels: list[str] = field(default_factory=list)


@dataclass
class DiscordGuildChannelConfig:
    allow: bool | None = None
    enabled: bool = True
    require_mention: bool | None = None
    tools: list[str] | None = None
    tools_by_sender: dict[str, list[str]] = field(default_factory=dict)
    skills: list[str] | None = None
    users: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    system_prompt: str | None = None
    include_thread_starter: bool = True
    auto_thread: bool | str | None = None
    reaction_notifications: ReactionNotifications = "own"


@dataclass
class DiscordGuildEntry:
    slug: str | None = None
    require_mention: bool | None = None
    tools: list[str] | None = None
    tools_by_sender: dict[str, list[str]] = field(default_factory=dict)
    reaction_notifications: ReactionNotifications = "own"
    users: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    channels: dict[str, DiscordGuildChannelConfig] = field(default_factory=dict)


@dataclass
class BlockStreamingCoalesceConfig:
    min_chars: int = 1500
    idle_ms: int = 1000


@dataclass
class BlockStreamingChunkConfig:
    min_chars: int | None = None
    idle_ms: int | None = None


@dataclass
class VoiceAutoJoinEntry:
    guild_id: str = ""
    channel_id: str = ""


@dataclass
class TtsConfig:
    provider: str | None = None
    voice: str | None = None
    model: str | None = None


@dataclass
class VoiceConfig:
    enabled: bool = True
    auto_join: list[VoiceAutoJoinEntry] = field(default_factory=list)
    dave_encryption: bool = True
    decryption_failure_tolerance: int = 24
    tts: TtsConfig = field(default_factory=TtsConfig)


@dataclass
class ThreadBindingsConfig:
    enabled: bool = True
    idle_hours: int = 24
    max_age_hours: int = 0
    spawn_subagent_sessions: bool = False
    spawn_acp_sessions: bool = False


@dataclass
class ExecApprovalsConfig:
    enabled: bool = False
    approvers: list[str] = field(default_factory=list)
    agent_filter: list[str] | None = None
    session_filter: list[str] | None = None
    cleanup_after_resolve: bool = True
    target: ExecApprovalTarget = "dm"


@dataclass
class PluralKitConfig:
    enabled: bool = False


@dataclass
class DiscordMarkdownConfig:
    tables: bool = True


@dataclass
class DiscordIntentsConfig:
    presence: bool = False
    guild_members: bool = False


@dataclass
class DiscordEventQueueConfig:
    listener_timeout: int = 120000
    max_queue_size: int = 10000
    max_concurrency: int = 50


@dataclass
class DiscordSlashCommandConfig:
    ephemeral: bool = True


@dataclass
class DiscordUiComponentsConfig:
    accent_color: str | None = None


@dataclass
class DiscordUiConfig:
    components: DiscordUiComponentsConfig = field(default_factory=DiscordUiComponentsConfig)


@dataclass
class DiscordRetryConfig:
    max_attempts: int = 3
    base_delay_ms: int = 1000


@dataclass
class ResolvedDiscordAccount:
    """Fully resolved (merged) config for a single Discord account."""

    account_id: str
    token: str
    enabled: bool
    name: str | None
    # DM
    dm: DiscordDmConfig
    # Group/Guild
    group_policy: GroupPolicy
    guilds: dict[str, DiscordGuildEntry]
    # Allowlist/access
    allow_bots: bool
    dangerously_allow_name_matching: bool
    # Streaming
    streaming: StreamingMode
    block_streaming_coalesce: BlockStreamingCoalesceConfig
    draft_chunk: BlockStreamingChunkConfig
    text_chunk_limit: int
    max_lines_per_message: int
    chunk_mode: Literal["length", "newline"]
    # Voice
    voice: VoiceConfig
    # Threading
    thread_bindings: ThreadBindingsConfig
    # Exec approvals
    exec_approvals: ExecApprovalsConfig
    # PluralKit
    pluralkit: PluralKitConfig
    # Presence
    activity: str | None
    status: Literal["online", "dnd", "idle", "invisible"] | None
    activity_type: ActivityType
    activity_url: str | None
    # Reactions / ack
    ack_reaction: str | None
    ack_reaction_scope: AckReactionScope
    reply_to_mode: ReplyToMode
    # Media / history
    media_max_mb: int
    history_limit: int
    # UI / misc
    allow_config_writes: bool
    slash_command: DiscordSlashCommandConfig
    ui: DiscordUiConfig
    markdown: DiscordMarkdownConfig
    intents: DiscordIntentsConfig
    event_queue: DiscordEventQueueConfig
    retry: DiscordRetryConfig
    proxy: str | None
    default_to: str | None
    response_prefix: str | None
    # Raw extra capabilities tags
    capabilities_tags: list[str]


def _parse_dm(raw: dict[str, Any]) -> DiscordDmConfig:
    dm_raw = raw.get("dm") or {}
    return DiscordDmConfig(
        enabled=dm_raw.get("enabled", raw.get("dm_enabled", True)),
        policy=dm_raw.get("policy") or raw.get("dm_policy") or raw.get("dmPolicy", "pairing"),
        allow_from=dm_raw.get("allowFrom") or dm_raw.get("allow_from") or raw.get("allowFrom") or raw.get("allow_from", []),
        group_enabled=dm_raw.get("groupEnabled", dm_raw.get("group_enabled", False)),
        group_channels=dm_raw.get("groupChannels") or dm_raw.get("group_channels", []),
    )


def _parse_guild_channel(raw: dict[str, Any]) -> DiscordGuildChannelConfig:
    return DiscordGuildChannelConfig(
        allow=raw.get("allow"),
        enabled=raw.get("enabled", True),
        require_mention=raw.get("requireMention") if raw.get("requireMention") is not None else raw.get("require_mention"),
        tools=raw.get("tools"),
        tools_by_sender=raw.get("toolsBySender") or raw.get("tools_by_sender", {}),
        skills=raw.get("skills"),
        users=raw.get("users", []),
        roles=raw.get("roles", []),
        system_prompt=raw.get("systemPrompt") or raw.get("system_prompt"),
        include_thread_starter=raw.get("includeThreadStarter", raw.get("include_thread_starter", True)),
        auto_thread=raw.get("autoThread") if raw.get("autoThread") is not None else raw.get("auto_thread"),
        reaction_notifications=raw.get("reactionNotifications") or raw.get("reaction_notifications", "own"),
    )


def _parse_guild_entry(raw: dict[str, Any]) -> DiscordGuildEntry:
    channels_raw = raw.get("channels") or {}
    return DiscordGuildEntry(
        slug=raw.get("slug"),
        require_mention=raw.get("requireMention") if raw.get("requireMention") is not None else raw.get("require_mention"),
        tools=raw.get("tools"),
        tools_by_sender=raw.get("toolsBySender") or raw.get("tools_by_sender", {}),
        reaction_notifications=raw.get("reactionNotifications") or raw.get("reaction_notifications", "own"),
        users=raw.get("users", []),
        roles=raw.get("roles", []),
        channels={k: _parse_guild_channel(v) for k, v in channels_raw.items() if isinstance(v, dict)},
    )


def _parse_voice(raw: dict[str, Any]) -> VoiceConfig:
    v = raw.get("voice") or {}
    auto_join_raw = v.get("autoJoin") or v.get("auto_join", [])
    auto_join = [
        VoiceAutoJoinEntry(
            guild_id=str(e.get("guildId") or e.get("guild_id", "")),
            channel_id=str(e.get("channelId") or e.get("channel_id", "")),
        )
        for e in (auto_join_raw if isinstance(auto_join_raw, list) else [])
    ]
    tts_raw = v.get("tts") or {}
    return VoiceConfig(
        enabled=v.get("enabled", True),
        auto_join=auto_join,
        dave_encryption=v.get("daveEncryption", v.get("dave_encryption", True)),
        decryption_failure_tolerance=v.get("decryptionFailureTolerance", v.get("decryption_failure_tolerance", 24)),
        tts=TtsConfig(
            provider=tts_raw.get("provider"),
            voice=tts_raw.get("voice"),
            model=tts_raw.get("model"),
        ),
    )


def _parse_thread_bindings(raw: dict[str, Any]) -> ThreadBindingsConfig:
    tb = raw.get("threadBindings") or raw.get("thread_bindings") or {}
    return ThreadBindingsConfig(
        enabled=tb.get("enabled", True),
        idle_hours=tb.get("idleHours", tb.get("idle_hours", 24)),
        max_age_hours=tb.get("maxAgeHours", tb.get("max_age_hours", 0)),
        spawn_subagent_sessions=tb.get("spawnSubagentSessions", tb.get("spawn_subagent_sessions", False)),
        spawn_acp_sessions=tb.get("spawnAcpSessions", tb.get("spawn_acp_sessions", False)),
    )


def _parse_exec_approvals(raw: dict[str, Any]) -> ExecApprovalsConfig:
    ea = raw.get("execApprovals") or raw.get("exec_approvals") or {}
    return ExecApprovalsConfig(
        enabled=ea.get("enabled", False),
        approvers=ea.get("approvers", []),
        agent_filter=ea.get("agentFilter") or ea.get("agent_filter"),
        session_filter=ea.get("sessionFilter") or ea.get("session_filter"),
        cleanup_after_resolve=ea.get("cleanupAfterResolve", ea.get("cleanup_after_resolve", True)),
        target=ea.get("target", "dm"),
    )


def _coerce_streaming(val: Any) -> StreamingMode:
    if val is True or val == "partial" or val == "progress":
        return "partial"
    if val == "block":
        return "block"
    if val is False or val == "off":
        return "off"
    return "partial"


def _resolve_account(account_id: str, raw: dict[str, Any], top: dict[str, Any]) -> ResolvedDiscordAccount:
    """Merge top-level defaults with per-account overrides."""
    merged: dict[str, Any] = {**top, **raw}

    token = (
        raw.get("token")
        or top.get("token")
        or os.environ.get(f"DISCORD_BOT_TOKEN_{account_id.upper()}")
        or os.environ.get("DISCORD_BOT_TOKEN", "")
    )

    bsc_raw = merged.get("blockStreamingCoalesce") or merged.get("block_streaming_coalesce") or {}
    draft_raw = merged.get("draftChunk") or merged.get("draft_chunk") or {}
    slash_raw = merged.get("slashCommand") or merged.get("slash_command") or {}
    ui_raw = merged.get("ui") or {}
    ui_comp_raw = ui_raw.get("components") or {}
    md_raw = merged.get("markdown") or {}
    intents_raw = merged.get("intents") or {}
    eq_raw = merged.get("eventQueue") or merged.get("event_queue") or {}
    retry_raw = merged.get("retry") or {}
    guilds_raw = merged.get("guilds") or {}

    return ResolvedDiscordAccount(
        account_id=account_id,
        token=token,
        enabled=merged.get("enabled", True),
        name=merged.get("name"),
        dm=_parse_dm(merged),
        group_policy=merged.get("groupPolicy") or merged.get("group_policy", "open"),
        guilds={k: _parse_guild_entry(v) for k, v in guilds_raw.items() if isinstance(v, dict)},
        allow_bots=merged.get("allowBots", merged.get("allow_bots", False)),
        dangerously_allow_name_matching=merged.get("dangerouslyAllowNameMatching", merged.get("dangerously_allow_name_matching", False)),
        streaming=_coerce_streaming(merged.get("streaming")),
        block_streaming_coalesce=BlockStreamingCoalesceConfig(
            min_chars=bsc_raw.get("minChars", bsc_raw.get("min_chars", 1500)),
            idle_ms=bsc_raw.get("idleMs", bsc_raw.get("idle_ms", 1000)),
        ),
        draft_chunk=BlockStreamingChunkConfig(
            min_chars=draft_raw.get("minChars") or draft_raw.get("min_chars"),
            idle_ms=draft_raw.get("idleMs") or draft_raw.get("idle_ms"),
        ),
        text_chunk_limit=int(merged.get("textChunkLimit") or merged.get("text_chunk_limit") or 2000),
        max_lines_per_message=int(merged.get("maxLinesPerMessage") or merged.get("max_lines_per_message") or 17),
        chunk_mode=merged.get("chunkMode") or merged.get("chunk_mode", "length"),
        voice=_parse_voice(merged),
        thread_bindings=_parse_thread_bindings(merged),
        exec_approvals=_parse_exec_approvals(merged),
        pluralkit=PluralKitConfig(enabled=bool((merged.get("pluralkit") or {}).get("enabled", False))),
        activity=merged.get("activity"),
        status=merged.get("status"),
        activity_type=int(merged.get("activityType") or merged.get("activity_type") or 0),
        activity_url=merged.get("activityUrl") or merged.get("activity_url"),
        ack_reaction=merged.get("ackReaction") or merged.get("ack_reaction"),
        ack_reaction_scope=merged.get("ackReactionScope") or merged.get("ack_reaction_scope", "group-mentions"),
        reply_to_mode=merged.get("replyToMode") or merged.get("reply_to_mode", "off"),
        media_max_mb=int(merged.get("mediaMaxMb") or merged.get("media_max_mb") or 8),
        history_limit=int(merged.get("historyLimit") or merged.get("history_limit") or 20),
        allow_config_writes=merged.get("configWrites", merged.get("allow_config_writes", True)),
        slash_command=DiscordSlashCommandConfig(ephemeral=slash_raw.get("ephemeral", True)),
        ui=DiscordUiConfig(
            components=DiscordUiComponentsConfig(accent_color=ui_comp_raw.get("accentColor") or ui_comp_raw.get("accent_color")),
        ),
        markdown=DiscordMarkdownConfig(tables=md_raw.get("tables", True)),
        intents=DiscordIntentsConfig(
            presence=intents_raw.get("presence", False),
            guild_members=intents_raw.get("guildMembers", intents_raw.get("guild_members", False)),
        ),
        event_queue=DiscordEventQueueConfig(
            listener_timeout=eq_raw.get("listenerTimeout", eq_raw.get("listener_timeout", 120000)),
            max_queue_size=eq_raw.get("maxQueueSize", eq_raw.get("max_queue_size", 10000)),
            max_concurrency=eq_raw.get("maxConcurrency", eq_raw.get("max_concurrency", 50)),
        ),
        retry=DiscordRetryConfig(
            max_attempts=retry_raw.get("maxAttempts", retry_raw.get("max_attempts", 3)),
            base_delay_ms=retry_raw.get("baseDelayMs", retry_raw.get("base_delay_ms", 1000)),
        ),
        proxy=merged.get("proxy"),
        default_to=merged.get("defaultTo") or merged.get("default_to"),
        response_prefix=merged.get("responsePrefix") or merged.get("response_prefix"),
        capabilities_tags=merged.get("capabilities") or [],
    )


def parse_discord_config(config: dict[str, Any]) -> list[ResolvedDiscordAccount]:
    """
    Parse raw config dict into a list of resolved Discord accounts.
    Mirrors the multi-account merging logic of the TS discordAccountsFromConfig.
    """
    accounts_raw: dict[str, Any] = config.get("accounts") or {}
    default_account: str = config.get("defaultAccount") or config.get("default_account", "default")

    # Top-level acts as defaults for all accounts
    top = {k: v for k, v in config.items() if k not in ("accounts", "defaultAccount", "default_account")}

    resolved: list[ResolvedDiscordAccount] = []

    if accounts_raw:
        for acct_id, acct_raw in accounts_raw.items():
            if isinstance(acct_raw, dict):
                resolved.append(_resolve_account(acct_id, acct_raw, top))
    else:
        # Single-account mode: treat entire config as one account
        token = config.get("token") or os.environ.get("DISCORD_BOT_TOKEN", "")
        if token:
            resolved.append(_resolve_account(default_account, config, {}))

    return [a for a in resolved if a.enabled]
