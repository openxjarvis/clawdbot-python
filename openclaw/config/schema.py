"""Configuration schema using Pydantic (aligned with TypeScript OpenClawConfig)"""
from __future__ import annotations

import builtins

from pydantic import BaseModel, ConfigDict, Field
from typing import Any, Literal


class ModelConfig(BaseModel):
    """Model configuration"""
    primary: str = Field(default="anthropic/claude-opus-4-5-20250514")
    fallbacks: list[str] = Field(default_factory=list)


class AgentConfig(BaseModel):
    """Agent configuration"""
    model: str | ModelConfig = Field(default="anthropic/claude-opus-4-5-20250514")
    thinking: str | None = Field(default=None)
    verbose: bool = Field(default=False)
    compaction: CompactionConfig | None = Field(default=None)
    contextPruning: ContextPruningConfig | None = Field(default=None)
    maxHistoryTurns: int = Field(default=50, ge=1)
    maxHistoryShare: float = Field(default=0.5, ge=0.1, le=0.9)


class AuthConfig(BaseModel):
    """Gateway authentication configuration"""
    mode: str = Field(default="token")
    token: str | None = Field(default=None)
    password: str | None = Field(default=None)
    allow_tailscale: bool | None = Field(default=None, alias="allowTailscale")
    trusted_proxy: dict[str, Any] | None = Field(default=None, alias="trustedProxy")


class GatewayNodesConfig(BaseModel):
    """Gateway nodes configuration"""
    browser: dict[str, Any] | None = Field(default=None)
    allow_commands: list[str] | None = Field(default=None, alias="allowCommands")
    deny_commands: list[str] | None = Field(default=None, alias="denyCommands")


class GatewayTailscaleConfig(BaseModel):
    """Gateway Tailscale configuration"""
    mode: str = Field(default="off")  # "off" | "serve" | "funnel"
    reset_on_exit: bool = Field(default=False, alias="resetOnExit")


class GatewayConfig(BaseModel):
    """Gateway server configuration (aligned with TypeScript)"""
    port: int = Field(default=18789)
    bind: str = Field(default="loopback")
    mode: str = Field(default="local")
    auth: AuthConfig | None = Field(default=None)
    trusted_proxies: list[str] = Field(default_factory=list, alias="trustedProxies")
    enable_web_ui: bool = Field(default=True, alias="enableWebUI")
    web_ui_port: int = Field(default=8080, alias="webUIPort")
    web_ui_base_path: str = Field(default="/", alias="webUIBasePath")
    nodes: GatewayNodesConfig | None = Field(default=None)
    tailscale: GatewayTailscaleConfig | None = Field(default=None)


class ApplyPatchConfig(BaseModel):
    """apply_patch tool sub-configuration (aligned with TS ExecToolConfig.applyPatch)"""
    enabled: bool = Field(default=True)
    workspace_only: bool = Field(default=True, alias="workspaceOnly")
    allow_models: list[str] | None = Field(default=None, alias="allowModels")

    model_config = {"populate_by_name": True}


class ExecToolConfig(BaseModel):
    """Exec tool configuration (fully aligned with TS ExecToolConfig)"""
    host: str = Field(default="gateway")          # "sandbox" | "gateway" | "node"
    security: str = Field(default="deny")         # TS default: "deny"
    ask: str = Field(default="on-miss")           # TS default: "on-miss"
    ask_fallback: str = Field(default="deny", alias="askFallback")
    node: str | None = Field(default=None)        # bound node id for host=node
    safe_bins: list[str] = Field(
        default_factory=lambda: ["python", "pip", "git", "node", "npm"],
        alias="safeBins",
    )
    safe_bin_trusted_dirs: list[str] = Field(default_factory=list, alias="safeBinTrustedDirs")
    safe_bin_profiles: dict[str, Any] = Field(default_factory=dict, alias="safeBinProfiles")
    path_prepend: list[str] = Field(default_factory=list, alias="pathPrepend")
    timeout_sec: int = Field(default=120, alias="timeoutSec")
    background_ms: int = Field(default=10_000, alias="backgroundMs")       # auto-background after N ms
    approval_running_notice_ms: int = Field(default=10_000, alias="approvalRunningNoticeMs")
    cleanup_ms: int = Field(default=1_800_000, alias="cleanupMs")           # 30 min TTL for finished sessions
    notify_on_exit: bool = Field(default=False, alias="notifyOnExit")
    notify_on_exit_empty_success: bool = Field(default=False, alias="notifyOnExitEmptySuccess")
    apply_patch: ApplyPatchConfig = Field(default_factory=ApplyPatchConfig, alias="applyPatch")

    model_config = {"populate_by_name": True}


class AgentToAgentConfig(BaseModel):
    """Agent-to-agent routing configuration (aligned with TS)"""
    enabled: bool = Field(default=False)
    allow: list[str] = Field(default_factory=list)
    maxPingPongTurns: int = Field(default=5, ge=0, le=5)


class SessionsToolsConfig(BaseModel):
    """Sessions tools visibility configuration (aligned with TS)"""
    visibility: str = Field(default="tree")  # "self" | "tree" | "agent" | "all"


class ElevatedAllowFromEntry(BaseModel):
    """Per-provider sender allowlist for /elevated mode"""
    provider: str
    senders: list[str] = Field(default_factory=list)


class ElevatedConfig(BaseModel):
    """Elevated mode configuration (aligned with TS elevated config)"""
    enabled: bool = Field(default=False)
    allow_from: list[ElevatedAllowFromEntry] | None = Field(default=None, alias="allowFrom")

    model_config = {"populate_by_name": True}


class ToolPolicyConfig(BaseModel):
    """Per-provider or per-sender tool policy (aligned with TS ToolPolicyConfig)"""
    allow: list[str] | None = Field(default=None)
    also_allow: list[str] | None = Field(default=None, alias="alsoAllow")
    deny: list[str] | None = Field(default=None)
    profile: str | None = Field(default=None)

    model_config = {"populate_by_name": True}


class LoopDetectionConfig(BaseModel):
    """Tool loop detection configuration (aligned with TS ToolLoopDetectionConfig)"""
    enabled: bool = Field(default=True)
    window: int = Field(default=10)
    threshold: int = Field(default=5)


class MessageCrossContextConfig(BaseModel):
    """Cross-context message send permissions (aligned with TS)"""
    allow_within_provider: bool = Field(default=True, alias="allowWithinProvider")
    allow_across_providers: bool = Field(default=False, alias="allowAcrossProviders")

    model_config = {"populate_by_name": True}


class SubagentsToolsConfig(BaseModel):
    """Subagent tool policy defaults (aligned with TS subagents.tools)"""
    allow: list[str] | None = Field(default=None)
    also_allow: list[str] | None = Field(default=None, alias="alsoAllow")
    deny: list[str] | None = Field(default=None)

    model_config = {"populate_by_name": True}


class SandboxToolsConfig(BaseModel):
    """Sandbox tool policy at ToolsConfig level (aligned with TS sandbox.tools)"""
    allow: list[str] | None = Field(default=None)
    deny: list[str] | None = Field(default=None)


class FsToolsConfig(BaseModel):
    """Filesystem tool restrictions (aligned with TS FsToolsConfig)"""
    workspace_only: bool = Field(default=False, alias="workspaceOnly")

    model_config = {"populate_by_name": True}


class ToolsConfig(BaseModel):
    """Tools configuration (aligned with TypeScript ToolsConfig)"""
    profile: str = Field(default="full")
    allow: list[str] | None = Field(default=None)
    also_allow: list[str] | None = Field(default=None, alias="alsoAllow")
    deny: list[str] | None = Field(default=None)
    by_provider: dict[str, ToolPolicyConfig] | None = Field(default=None, alias="byProvider")
    elevated: ElevatedConfig | None = Field(default=None)
    exec: ExecToolConfig | None = Field(default_factory=ExecToolConfig)
    fs: FsToolsConfig | None = Field(default=None)
    subagents: SubagentsToolsConfig | None = Field(default=None)
    sandbox: SandboxToolsConfig | None = Field(default=None)
    loop_detection: LoopDetectionConfig | None = Field(default=None, alias="loopDetection")
    sessions: SessionsToolsConfig | None = Field(default=None)
    message: MessageCrossContextConfig | None = Field(default=None)
    agentToAgent: AgentToAgentConfig | None = Field(default=None)

    model_config = {"populate_by_name": True}


class SoftTrimConfig(BaseModel):
    """Soft trim configuration for context pruning"""
    maxChars: int = Field(default=4000)
    headChars: int = Field(default=1500)
    tailChars: int = Field(default=1500)


class HardClearConfig(BaseModel):
    """Hard clear configuration for context pruning"""
    enabled: bool = Field(default=True)
    placeholder: str = Field(default="[Old tool result content cleared]")


class ContextPruningToolsConfig(BaseModel):
    """Tools configuration for context pruning"""
    prunable: list[str] = Field(default_factory=lambda: ["Read", "Grep", "Shell"])


class ContextPruningConfig(BaseModel):
    """Context pruning configuration - mirrors TypeScript AgentContextPruningConfig"""
    mode: str = Field(default="off")  # "off" | "cache-ttl"
    ttl: str | None = Field(default="5m")
    softTrimRatio: float = Field(default=0.3, ge=0.0, le=1.0)
    hardClearRatio: float = Field(default=0.5, ge=0.0, le=1.0)
    keepLastAssistants: int = Field(default=3, ge=0)
    softTrim: SoftTrimConfig = Field(default_factory=SoftTrimConfig)
    hardClear: HardClearConfig = Field(default_factory=HardClearConfig)
    tools: ContextPruningToolsConfig = Field(default_factory=ContextPruningToolsConfig)
    minPrunableToolChars: int = Field(default=50000, ge=0)


class CompactionConfig(BaseModel):
    """Compaction configuration - mirrors TypeScript AgentCompactionConfig"""
    enabled: bool = Field(default=True)
    mode: str = Field(default="safeguard")  # "default" | "safeguard"
    reserveTokens: int = Field(default=16384, ge=0)
    keepRecentTokens: int = Field(default=20000, ge=0)
    maxHistoryShare: float = Field(default=0.5, ge=0.1, le=0.9)
    reserveTokensFloor: int | None = Field(default=None, ge=0)


class AgentDefaults(BaseModel):
    """Default agent settings"""

    workspace: str | None = Field(default=None)
    agentDir: str | None = Field(default=None)
    model: str | ModelConfig = Field(default="google/gemini-3-pro-preview")
    models: dict[str, Any] | None = Field(default=None)
    tools: ToolsConfig | None = Field(default=None)
    compaction: CompactionConfig | None = Field(default=None)
    contextPruning: ContextPruningConfig | None = Field(default=None)
    maxHistoryTurns: int = Field(default=50, ge=1)
    maxHistoryShare: float = Field(default=0.5, ge=0.1, le=0.9)
    maxConcurrent: int | None = Field(default=None)
    subagents: "SubagentsConfig | None" = Field(default=None)


class IdentityConfig(BaseModel):
    """Agent identity configuration (aligned with TS)"""
    name: str | None = Field(default=None)
    theme: str | None = Field(default=None)
    emoji: str | None = Field(default=None)
    avatar: str | None = Field(default=None)
    creature: str | None = Field(default=None)
    vibe: str | None = Field(default=None)


class SandboxDockerConfig(BaseModel):
    """Docker-level sandbox configuration (aligned with TS SandboxDockerSettings)."""
    image: str | None = Field(default=None)
    container_prefix: str | None = Field(default=None, alias="containerPrefix")
    workdir: str | None = Field(default=None)
    read_only_root: bool | None = Field(default=None, alias="readOnlyRoot")
    tmpfs: list[str] | None = Field(default=None)
    network: str | None = Field(default=None)
    user: str | None = Field(default=None)
    cap_drop: list[str] | None = Field(default=None, alias="capDrop")
    env: dict[str, str] | None = Field(default=None)
    setup_command: str | None = Field(default=None, alias="setupCommand")
    pids_limit: int | None = Field(default=None, alias="pidsLimit")
    memory: str | int | None = Field(default=None)
    memory_swap: str | int | None = Field(default=None, alias="memorySwap")
    cpus: float | None = Field(default=None)
    ulimits: dict[str, Any] | None = Field(default=None)
    seccomp_profile: str | None = Field(default=None, alias="seccompProfile")
    apparmor_profile: str | None = Field(default=None, alias="apparmorProfile")
    dns: list[str] | None = Field(default=None)
    extra_hosts: list[str] | None = Field(default=None, alias="extraHosts")
    binds: list[str] = Field(default_factory=list)
    dangerously_allow_reserved_container_targets: bool = Field(
        default=False, alias="dangerouslyAllowReservedContainerTargets"
    )
    dangerously_allow_external_bind_sources: bool = Field(
        default=False, alias="dangerouslyAllowExternalBindSources"
    )
    dangerously_allow_container_namespace_join: bool = Field(
        default=False, alias="dangerouslyAllowContainerNamespaceJoin"
    )

    model_config = {"populate_by_name": True}


class SandboxBrowserConfig(BaseModel):
    """Sandbox browser configuration."""
    autoStart: bool = Field(default=True)
    autoStartTimeoutMs: int = Field(default=10_000)
    allowHostControl: bool = Field(default=False)
    allowedControlUrls: list[str] | None = Field(default=None)
    allowedControlHosts: list[str] | None = Field(default=None)
    allowedControlPorts: list[int] | None = Field(default=None)
    binds: list[str] | None = Field(default=None)


class SandboxConfig(BaseModel):
    """Sandbox configuration.

    Mirrors TS agents.defaults.sandbox / agents.list[].sandbox schema.
    See: openclaw/docs/gateway/sandboxing.md
    """

    # When to sandbox: "off" | "non-main" | "all"
    mode: str = Field(default="off")

    # Container scope: "session" | "agent" | "shared"
    scope: str = Field(default="session")

    # Workspace access inside sandbox: "none" | "ro" | "rw"
    workspaceAccess: str = Field(default="none")

    # Docker-level settings (bind mounts etc.)
    docker: SandboxDockerConfig = Field(default_factory=SandboxDockerConfig)

    # Optional browser sandbox
    browser: SandboxBrowserConfig | None = Field(default=None)

    # Legacy field kept for backward compat
    sessionToolsVisibility: str = Field(default="spawned")  # "spawned" | "all"


class SubagentsConfig(BaseModel):
    """Subagents configuration (aligned with TS subagents schema)"""
    maxConcurrent: int | None = Field(default=None)
    maxSpawnDepth: int = Field(default=1, ge=1, le=5)
    maxChildrenPerAgent: int = Field(default=5, ge=1, le=20)
    archiveAfterMinutes: int = Field(default=60, ge=1)
    model: str | ModelConfig | None = Field(default=None)
    thinking: str | None = Field(default=None)
    
    # Legacy fields for backward compatibility
    enabled: bool = Field(default=True, exclude=True)
    maxDepth: int | None = Field(default=None, exclude=True)
    maxActive: int | None = Field(default=None, exclude=True)
    
    def model_post_init(self, __context: object) -> None:
        """Migrate legacy fields"""
        if self.maxDepth is not None:
            self.maxSpawnDepth = self.maxDepth
        if self.maxActive is not None:
            self.maxChildrenPerAgent = self.maxActive


class GroupChatConfig(BaseModel):
    """Group chat configuration (aligned with TS GroupChatSchema)"""
    mentionPatterns: list[str] | None = Field(default=None)
    historyLimit: int | None = Field(default=None, ge=0)


class AgentEntry(BaseModel):
    """Individual agent configuration (aligned with TS)"""

    id: str
    default: bool = Field(default=False)
    name: str | None = Field(default=None)
    workspace: str | None = Field(default=None)
    agentDir: str | None = Field(default=None)
    model: str | ModelConfig | None = Field(default=None)
    tools: ToolsConfig | None = Field(default=None)
    identity: IdentityConfig | None = Field(default=None)
    sandbox: SandboxConfig | None = Field(default=None)
    subagents: SubagentsConfig | None = Field(default=None)
    groupChat: GroupChatConfig | None = Field(default=None)


class AgentsConfig(BaseModel):
    """Agents configuration (aligned with TS)"""

    model_config = ConfigDict(populate_by_name=True)

    defaults: AgentDefaults = Field(default_factory=AgentDefaults)
    # Use alias so JSON key "list" maps to agents_list (avoids shadowing builtin `list`)
    agents_list: builtins.list["AgentEntry"] | None = Field(default_factory=builtins.list, alias="list")

    # Support legacy "agents" field for backward compatibility
    agents: builtins.list["AgentEntry"] | None = Field(default=None, exclude=True)

    @property
    def list(self) -> builtins.list["AgentEntry"]:  # type: ignore[override]
        """Access agent list (TS compatibility: agents.list)"""
        return self.agents_list or []

    def model_post_init(self, __context: object) -> None:
        """Migrate legacy 'agents' field to agents_list"""
        if self.agents and not self.agents_list:
            self.agents_list = self.agents


class TelegramRetryConfig(BaseModel):
    """Telegram retry configuration"""
    attempts: int = Field(default=3, ge=1)
    minDelayMs: int = Field(default=1000, ge=0, alias="min_delay_ms")
    maxDelayMs: int = Field(default=30000, ge=0, alias="max_delay_ms")
    jitter: bool = Field(default=True)
    
    model_config = {"populate_by_name": True}


class TelegramNetworkConfig(BaseModel):
    """Telegram network configuration"""
    autoSelectFamily: bool | None = Field(default=None, alias="auto_select_family")
    dnsResultOrder: str | None = Field(default=None, alias="dns_result_order")
    
    model_config = {"populate_by_name": True}


class TelegramActionConfig(BaseModel):
    """Telegram action configuration"""
    reactions: bool = Field(default=True)
    sendMessage: bool = Field(default=True, alias="send_message")
    deleteMessage: bool = Field(default=True, alias="delete_message")
    editMessage: bool = Field(default=True, alias="edit_message")
    sticker: bool = Field(default=False)
    createForumTopic: bool = Field(default=False, alias="create_forum_topic")
    
    model_config = {"populate_by_name": True}


class TelegramDraftChunkConfig(BaseModel):
    """Draft chunk configuration for block streaming"""
    minChars: int = Field(default=100, ge=0, alias="min_chars")
    maxChars: int = Field(default=2000, ge=0, alias="max_chars")
    
    model_config = {"populate_by_name": True}


class TelegramTopicConfig(BaseModel):
    """Telegram forum topic configuration"""
    requireMention: bool | None = Field(default=None, alias="require_mention")
    groupPolicy: str | None = Field(default=None, alias="group_policy")
    skills: list[str] | None = Field(default=None)
    enabled: bool | None = Field(default=None)
    allowFrom: list[str | int] | None = Field(default=None, alias="allow_from")
    systemPrompt: str | None = Field(default=None, alias="system_prompt")
    
    model_config = {"populate_by_name": True}


class TelegramGroupConfig(BaseModel):
    """Telegram group configuration"""
    requireMention: bool | None = Field(default=None, alias="require_mention")
    groupPolicy: str | None = Field(default=None, alias="group_policy")
    skills: list[str] | None = Field(default=None)
    topics: dict[str, TelegramTopicConfig] | None = Field(default=None)
    enabled: bool | None = Field(default=None)
    allowFrom: list[str | int] | None = Field(default=None, alias="allow_from")
    systemPrompt: str | None = Field(default=None, alias="system_prompt")
    
    model_config = {"populate_by_name": True}


class TelegramDmConfig(BaseModel):
    """Per-DM configuration"""
    historyLimit: int | None = Field(default=None, alias="history_limit")
    
    model_config = {"populate_by_name": True}


class TelegramCapabilitiesConfig(BaseModel):
    """
    Telegram capabilities configuration (aligned with TS TelegramCapabilitiesConfig).
    Controls which features the bot exposes per chat type.
    """
    inline_buttons: str | None = Field(
        default=None,
        alias="inlineButtons",
        description=(
            "Inline button scope: off | dm | group | all | allowlist (default). "
            "Mirrors TS TelegramInlineButtonsScope."
        ),
    )

    model_config = {"populate_by_name": True}


class TelegramChannelConfig(BaseModel):
    """Telegram channel configuration"""

    model_config = {"populate_by_name": True}

    enabled: bool = Field(default=True)
    botToken: str | None = Field(default=None, alias="bot_token")
    tokenFile: str | None = Field(default=None, alias="token_file")
    allowFrom: list[str | int] | None = Field(default=None, alias="allow_from")
    groupAllowFrom: list[str | int] | None = Field(default=None, alias="group_allow_from")
    dmPolicy: str | None = Field(default=None, alias="dm_policy")
    groupPolicy: str | None = Field(default=None, alias="group_policy")
    replyToMode: str | None = Field(default=None, alias="reply_to_mode")
    
    # Streaming and chunking
    streamMode: str | None = Field(default=None, alias="stream_mode")
    draftChunk: TelegramDraftChunkConfig | None = Field(default=None, alias="draft_chunk")
    textChunkLimit: int | None = Field(default=None, alias="text_chunk_limit")
    chunkMode: str | None = Field(default=None, alias="chunk_mode")
    blockStreaming: bool | None = Field(default=None, alias="block_streaming")
    
    # Reactions
    reactionNotifications: str | None = Field(default=None, alias="reaction_notifications")
    reactionLevel: str | None = Field(default=None, alias="reaction_level")
    ackReaction: str | None = Field(default=None, alias="ack_reaction")
    
    # History
    historyLimit: int | None = Field(default=None, alias="history_limit")
    dmHistoryLimit: int | None = Field(default=None, alias="dm_history_limit")
    dms: dict[str, TelegramDmConfig] | None = Field(default=None)
    
    # Groups and topics
    groups: dict[str, TelegramGroupConfig] | None = Field(default=None)
    
    # Webhook
    webhookUrl: str | None = Field(default=None, alias="webhook_url")
    webhookSecret: str | None = Field(default=None, alias="webhook_secret")
    webhookPath: str | None = Field(default=None, alias="webhook_path")
    webhookHost: str | None = Field(default=None, alias="webhook_host")
    
    # Network and retry
    retry: TelegramRetryConfig | None = Field(default=None)
    network: TelegramNetworkConfig | None = Field(default=None)
    proxy: str | None = Field(default=None)
    timeoutSeconds: int | None = Field(default=None, alias="timeout_seconds")
    
    # Actions
    actions: TelegramActionConfig | None = Field(default=None)
    
    # Media
    mediaMaxMb: int | None = Field(default=None, alias="media_max_mb")
    
    # Misc
    capabilities: TelegramCapabilitiesConfig | Any | None = Field(default=None)
    linkPreview: bool | None = Field(default=None, alias="link_preview")
    responsePrefix: str | None = Field(default=None, alias="response_prefix")
    configWrites: bool | None = Field(default=None, alias="config_writes")
    
    # Multi-account
    accounts: dict[str, Any] | None = Field(default=None)


class ChannelConfig(BaseModel):
    """Individual channel configuration (generic)"""

    enabled: bool = Field(default=True)
    botToken: str | None = Field(default=None, alias="bot_token")
    allowFrom: list[str] | None = Field(default=None, alias="allow_from")
    dmPolicy: str | None = Field(default=None, alias="dm_policy")

    # Additional platform-specific fields
    token: str | None = Field(default=None)
    signingSecret: str | None = Field(default=None, alias="signing_secret")
    appId: str | None = Field(default=None, alias="app_id")
    appSecret: str | None = Field(default=None, alias="app_secret")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class FeishuChannelConfig(BaseModel):
    """Feishu / Lark channel configuration (mirrors TS FeishuConfigSchema)"""

    enabled: bool = Field(default=True)
    appId: str | None = Field(default=None)
    appSecret: str | None = Field(default=None)
    useWebSocket: bool = Field(default=True)
    dmPolicy: str = Field(default="pairing")
    webhookPath: str | None = Field(default=None)
    allowFrom: list[str] | None = Field(default=None)

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ChannelsConfig(BaseModel):
    """Channels configuration (mirrors TS ChannelsSchema with .passthrough())"""

    telegram: TelegramChannelConfig | None = Field(default=None)
    whatsapp: ChannelConfig | None = Field(default=None)
    discord: ChannelConfig | None = Field(default=None)
    slack: ChannelConfig | None = Field(default=None)
    feishu: FeishuChannelConfig | None = Field(default=None)

    # Allow extension channels (matrix, zalo, msteams, etc.) — matches TS .passthrough()
    model_config = ConfigDict(extra="allow")


class SkillsConfig(BaseModel):
    """Skills configuration"""

    allowBundled: list[str] | None = Field(default=None)
    enable: list[str] | None = Field(default=None)
    disable: list[str] | None = Field(default=None)


class PluginEntryConfig(BaseModel):
    """Individual plugin entry configuration (mirrors TS plugins.entries[name])"""
    enabled: bool = Field(default=True)


class PluginsConfig(BaseModel):
    """Plugins configuration"""

    entries: dict[str, PluginEntryConfig] | None = Field(default=None)
    enable: list[str] | None = Field(default=None)
    disable: list[str] | None = Field(default=None)


class MetaConfig(BaseModel):
    """Metadata configuration"""
    last_touched_version: str | None = Field(default=None, alias="lastTouchedVersion")
    last_touched_at: str | None = Field(default=None, alias="lastTouchedAt")


class MessagesConfig(BaseModel):
    """Messages configuration (TS alignment)"""
    ack_reaction_scope: str | None = Field(default="group-mentions", alias="ackReactionScope")


class CommandsConfig(BaseModel):
    """Commands configuration (TS alignment)"""
    native: str | None = Field(default="auto")
    native_skills: str | None = Field(default="auto", alias="nativeSkills")


class WizardConfig(BaseModel):
    """Wizard run tracking"""
    last_run_at: str | None = Field(default=None, alias="lastRunAt")
    last_run_version: str | None = Field(default=None, alias="lastRunVersion")
    last_run_commit: str | None = Field(default=None, alias="lastRunCommit")
    last_run_command: str | None = Field(default=None, alias="lastRunCommand")
    last_run_mode: str | None = Field(default=None, alias="lastRunMode")


class LoggingConfig(BaseModel):
    """Logging configuration"""
    level: str = Field(default="INFO")
    format: str = Field(default="colored")


class UpdateConfig(BaseModel):
    """Update configuration"""
    channel: str = Field(default="stable")
    check_on_start: bool = Field(default=False, alias="checkOnStart")


class UIConfig(BaseModel):
    """UI configuration"""
    seam_color: str | None = Field(default=None, alias="seamColor")


class ModelsConfig(BaseModel):
    """Models configuration"""
    providers: dict[str, Any] | None = Field(default=None)


class MemoryConfig(BaseModel):
    """Memory configuration"""
    enabled: bool = Field(default=True)
    provider: str = Field(default="simple")


class CronConfig(BaseModel):
    """Cron configuration"""
    enabled: bool = Field(default=True)


class InternalHooksConfig(BaseModel):
    """Internal hooks configuration"""
    enabled: bool = Field(default=True)
    handlers: dict[str, Any] | None = Field(default=None)
    entries: dict[str, Any] | None = Field(default=None)
    load: dict[str, Any] | None = Field(default=None)
    installs: dict[str, Any] | None = Field(default=None)


class HooksConfig(BaseModel):
    """Hooks configuration — TS does not write top-level enabled; use None to omit it"""
    enabled: bool | None = Field(default=None)
    internal: InternalHooksConfig | None = Field(default=None)


class ShellEnvConfig(BaseModel):
    """Shell env import configuration (mirrors TS env.shellEnv)"""
    enabled: bool = Field(default=False)


class EnvConfig(BaseModel):
    """Environment variable configuration block in openclaw.json.

    Mirrors TS zod-schema.ts env block:
      env:
        GOOGLE_API_KEY: "AIza..."
        ANTHROPIC_API_KEY: "sk-ant-..."
        vars: { FOO: "bar" }
        shellEnv: { enabled: true }

    Any top-level key that is not a known sub-field is treated as a raw env var,
    applied to the process environment at startup (override: false — already-set
    vars from .env files or the shell take precedence).
    """
    vars: dict[str, str] | None = Field(default=None)
    shell_env: ShellEnvConfig | None = Field(default=None, alias="shellEnv")

    model_config = {"populate_by_name": True, "extra": "allow"}

    def get_all_vars(self) -> dict[str, str]:
        """Return all env var overrides as a flat dict.
        Merges ``vars`` dict and any extra top-level string fields.
        """
        result: dict[str, str] = {}
        if self.vars:
            result.update({k: v for k, v in self.vars.items() if v})
        for key, value in (self.model_extra or {}).items():
            if isinstance(value, str) and value.strip():
                result[key] = value
        return result


class SessionMaintenanceConfig(BaseModel):
    """Session maintenance configuration — mirrors TS session.maintenance schema."""
    model_config = ConfigDict(populate_by_name=True)

    pruneAfter: str | None = Field(default=None)
    pruneDays: int | None = Field(default=None)
    maxEntries: int | None = Field(default=None)
    rotateBytes: str | None = Field(default=None)
    maxDiskBytes: str | None = Field(default=None)
    highWaterBytes: str | None = Field(default=None)
    resetArchiveRetention: str | None = Field(default=None)


class SessionConfig(BaseModel):
    """Session configuration — mirrors TS zod-schema.session.ts.

    Replaces the previous ``dict[str, Any]`` field so that ``dmScope``,
    ``identityLinks``, and ``maintenance`` are accessible as typed attributes
    in ``resolve_agent_route()`` and elsewhere.
    """
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    dmScope: Literal["main", "per-peer", "per-channel-peer", "per-account-channel-peer"] = Field(
        default="main"
    )
    identityLinks: dict[str, list[str]] | None = Field(default=None)
    maintenance: SessionMaintenanceConfig = Field(default_factory=SessionMaintenanceConfig)
    reset: str | None = Field(default=None)
    idleMinutes: int | None = Field(default=None)
    resetByType: dict[str, Any] | None = Field(default=None)
    resetByChannel: dict[str, Any] | None = Field(default=None)
    store: str | None = Field(default=None)


class ClawdbotConfig(BaseModel):
    """Root configuration schema (aligned with TypeScript OpenClawConfig)"""
    
    # Core configs (original 7)
    agent: AgentConfig | None = Field(default_factory=AgentConfig)
    gateway: GatewayConfig | None = Field(default_factory=GatewayConfig)
    agents: AgentsConfig | None = Field(default_factory=AgentsConfig)
    channels: ChannelsConfig | None = Field(default_factory=ChannelsConfig)
    tools: ToolsConfig | None = Field(default_factory=ToolsConfig)
    skills: SkillsConfig | None = Field(default_factory=SkillsConfig)
    plugins: PluginsConfig | None = Field(default_factory=PluginsConfig)
    
    # Additional configs (matching TypeScript - 21 more fields)
    meta: MetaConfig | None = Field(default=None)
    auth: dict[str, Any] | None = Field(default=None)
    env: EnvConfig | dict[str, Any] | None = Field(default=None)
    wizard: WizardConfig | None = Field(default=None)
    diagnostics: dict[str, Any] | None = Field(default=None)
    logging: LoggingConfig | None = Field(default=None)
    update: UpdateConfig | None = Field(default=None)
    browser: dict[str, Any] | None = Field(default=None)
    ui: UIConfig | None = Field(default=None)
    models: ModelsConfig | None = Field(default=None)
    node_host: dict[str, Any] | None = Field(default=None, alias="nodeHost")
    bindings: list[dict[str, Any]] | None = Field(default=None)
    broadcast: dict[str, Any] | None = Field(default=None)
    audio: dict[str, Any] | None = Field(default=None)
    messages: MessagesConfig | None = Field(default=None)
    commands: CommandsConfig | None = Field(default=None)
    approvals: dict[str, Any] | None = Field(default=None)
    session: SessionConfig = Field(default_factory=SessionConfig)
    web: dict[str, Any] | None = Field(default=None)
    cron: CronConfig | None = Field(default=None)
    hooks: HooksConfig | None = Field(default=None)
    discovery: dict[str, Any] | None = Field(default=None)
    canvas_host: dict[str, Any] | None = Field(default=None, alias="canvasHost")
    talk: dict[str, Any] | None = Field(default=None)
    memory: MemoryConfig | None = Field(default=None)

    class Config:
        extra = "allow"  # Allow extra fields for extensibility
        populate_by_name = True  # Support camelCase aliases
