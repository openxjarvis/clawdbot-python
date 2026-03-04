"""Feishu channel configuration schema.

Mirrors TypeScript: extensions/feishu/src/config-schema.ts
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Domain helpers
# ---------------------------------------------------------------------------

FEISHU_DOMAIN = "https://open.feishu.cn"
LARK_DOMAIN = "https://open.larksuite.com"


def resolve_domain(domain: str | None) -> str:
    """Resolve domain string to base URL."""
    d = (domain or "feishu").strip()
    if d == "feishu":
        return FEISHU_DOMAIN
    if d == "lark":
        return LARK_DOMAIN
    if d.startswith("https://"):
        return d.rstrip("/")
    return FEISHU_DOMAIN


# ---------------------------------------------------------------------------
# Per-group config
# ---------------------------------------------------------------------------

@dataclass
class FeishuGroupConfig:
    """Per-group chat configuration overrides. Mirrors TS FeishuGroupSchema."""

    enabled: bool | None = None
    require_mention: bool | None = None
    allow_from: list[str] = field(default_factory=list)
    system_prompt: str | None = None
    tools: dict[str, Any] | None = None
    skills: list[str] = field(default_factory=list)
    group_session_scope: str | None = None   # "group"|"group_sender"|"group_topic"|"group_topic_sender"
    topic_session_mode: str | None = None    # "disabled"|"enabled" (deprecated)
    reply_in_thread: str | None = None       # "disabled"|"enabled"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FeishuGroupConfig:
        return cls(
            enabled=d.get("enabled"),
            require_mention=d.get("requireMention"),
            allow_from=[str(e) for e in (d.get("allowFrom") or [])],
            system_prompt=d.get("systemPrompt"),
            tools=d.get("tools"),
            skills=list(d.get("skills") or []),
            group_session_scope=d.get("groupSessionScope") or d.get("group_session_scope"),
            topic_session_mode=d.get("topicSessionMode") or d.get("topic_session_mode"),
            reply_in_thread=d.get("replyInThread") or d.get("reply_in_thread"),
        )


# ---------------------------------------------------------------------------
# Per-DM config
# ---------------------------------------------------------------------------

@dataclass
class FeishuDmConfig:
    """Per-DM user configuration overrides. Mirrors TS DmConfigSchema."""
    enabled: bool | None = None
    system_prompt: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FeishuDmConfig:
        return cls(
            enabled=d.get("enabled"),
            system_prompt=d.get("systemPrompt"),
        )


# ---------------------------------------------------------------------------
# Tools config
# ---------------------------------------------------------------------------

@dataclass
class FeishuToolsConfig:
    """Tools on/off flags. Mirrors TS FeishuToolsConfigSchema."""
    doc: bool = True
    chat: bool = True
    wiki: bool = True
    drive: bool = True
    perm: bool = False
    scopes: bool = True

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> FeishuToolsConfig:
        if not d:
            return cls()
        return cls(
            doc=bool(d.get("doc", True)),
            chat=bool(d.get("chat", True)),
            wiki=bool(d.get("wiki", True)),
            drive=bool(d.get("drive", True)),
            perm=bool(d.get("perm", False)),
            scopes=bool(d.get("scopes", True)),
        )


# ---------------------------------------------------------------------------
# Dynamic agent creation config
# ---------------------------------------------------------------------------

@dataclass
class DynamicAgentCreationConfig:
    """Dynamic per-DM agent creation. Mirrors TS DynamicAgentCreationSchema."""
    enabled: bool = False
    workspace_template: str | None = None
    agent_dir_template: str | None = None
    max_agents: int | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> DynamicAgentCreationConfig:
        if not d:
            return cls()
        return cls(
            enabled=bool(d.get("enabled", False)),
            workspace_template=d.get("workspaceTemplate"),
            agent_dir_template=d.get("agentDirTemplate"),
            max_agents=d.get("maxAgents"),
        )


# ---------------------------------------------------------------------------
# Block-streaming coalesce config
# ---------------------------------------------------------------------------

@dataclass
class BlockStreamingCoalesceConfig:
    enabled: bool = False
    min_delay_ms: int = 100
    max_delay_ms: int = 1000

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> BlockStreamingCoalesceConfig:
        if not d:
            return cls()
        return cls(
            enabled=bool(d.get("enabled", False)),
            min_delay_ms=int(d.get("minDelayMs", 100)),
            max_delay_ms=int(d.get("maxDelayMs", 1000)),
        )


# ---------------------------------------------------------------------------
# Markdown config
# ---------------------------------------------------------------------------

@dataclass
class MarkdownConfig:
    mode: str = "native"        # "native"|"escape"|"strip"
    table_mode: str = "native"  # "native"|"ascii"|"simple"

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> MarkdownConfig:
        if not d:
            return cls()
        return cls(
            mode=d.get("mode", "native"),
            table_mode=d.get("tableMode", "native"),
        )


# ---------------------------------------------------------------------------
# Resolved account config (merged top-level + per-account)
# ---------------------------------------------------------------------------

@dataclass
class ResolvedFeishuAccount:
    """Fully merged account configuration. Mirrors TS ResolvedFeishuAccount."""

    account_id: str
    app_id: str
    app_secret: str
    encrypt_key: str = ""
    verification_token: str = ""
    domain: str = "feishu"
    domain_url: str = FEISHU_DOMAIN
    connection_mode: str = "websocket"   # "websocket"|"webhook"
    webhook_path: str = "/feishu/events"
    webhook_host: str = "127.0.0.1"
    webhook_port: int = 3000

    # DM policy
    dm_policy: str = "pairing"           # "open"|"pairing"|"allowlist"
    allow_from: list[str] = field(default_factory=list)

    # Group policy
    group_policy: str = "allowlist"      # "open"|"allowlist"|"disabled"
    group_allow_from: list[str] = field(default_factory=list)
    group_sender_allow_from: list[str] = field(default_factory=list)
    require_mention: bool = True
    groups: dict[str, FeishuGroupConfig] = field(default_factory=dict)
    group_session_scope: str = "group"
    topic_session_mode: str = "disabled"
    reply_in_thread: str = "disabled"

    # History
    history_limit: int = 50
    dm_history_limit: int = 0

    # Per-DM config
    dms: dict[str, FeishuDmConfig] = field(default_factory=dict)

    # Message rendering
    render_mode: str = "auto"            # "auto"|"raw"|"card"
    streaming: bool = True
    text_chunk_limit: int = 4000
    chunk_mode: str = "length"           # "length"|"newline"
    media_max_mb: float = 30.0
    markdown: MarkdownConfig = field(default_factory=MarkdownConfig)
    block_streaming_coalesce: BlockStreamingCoalesceConfig = field(
        default_factory=BlockStreamingCoalesceConfig
    )

    # Features
    typing_indicator: bool = True
    resolve_sender_names: bool = True
    reaction_notifications: str = "own"  # "off"|"own"|"all"

    # Tools
    tools: FeishuToolsConfig = field(default_factory=FeishuToolsConfig)

    # Dynamic agent creation
    dynamic_agent_creation: DynamicAgentCreationConfig = field(
        default_factory=DynamicAgentCreationConfig
    )


# ---------------------------------------------------------------------------
# Config parser: raw dict → ResolvedFeishuAccount list
# ---------------------------------------------------------------------------

def _coalesce(*values: Any) -> Any:
    """Return first non-None value."""
    for v in values:
        if v is not None:
            return v
    return None


def _str_list(v: Any) -> list[str]:
    if not v:
        return []
    return [str(e).strip() for e in v if str(e).strip()]


def parse_feishu_config(cfg: dict[str, Any]) -> list[ResolvedFeishuAccount]:
    """
    Parse raw Feishu config dict into a list of ResolvedFeishuAccount.

    Mirrors TS resolveFeishuAccounts() logic in accounts.ts.
    """
    top = cfg  # top-level config dict

    # Build top-level defaults
    top_app_id = (top.get("appId") or top.get("app_id") or "").strip()
    top_app_secret = (top.get("appSecret") or top.get("app_secret") or "").strip()
    top_domain = top.get("domain", "feishu")
    # Also handle useWebSocket: bool (written by Python onboarding / FeishuChannelConfig schema)
    _use_ws = top.get("useWebSocket")
    _ws_default = "websocket" if (_use_ws is None or _use_ws) else "webhook"
    top_connection_mode = top.get("connectionMode") or top.get("connection_mode") or _ws_default
    top_webhook_path = top.get("webhookPath") or top.get("webhook_path") or "/feishu/events"
    top_webhook_host = top.get("webhookHost") or top.get("webhook_host") or "127.0.0.1"
    top_webhook_port = int(top.get("webhookPort") or top.get("webhook_port") or 3000)

    accounts_dict: dict[str, Any] = top.get("accounts") or {}

    results: list[ResolvedFeishuAccount] = []

    def build_account(account_id: str, overrides: dict[str, Any] | None) -> ResolvedFeishuAccount | None:
        ov = overrides or {}

        app_id = (
            (ov.get("appId") or ov.get("app_id") or "").strip() or top_app_id
        )
        app_secret = (
            (ov.get("appSecret") or ov.get("app_secret") or "").strip() or top_app_secret
        )
        if not app_id or not app_secret:
            return None

        domain = _coalesce(ov.get("domain"), top_domain, "feishu")
        _ov_use_ws = ov.get("useWebSocket")
        _ov_cm = (
            ov.get("connectionMode") or ov.get("connection_mode")
            or (None if _ov_use_ws is None else ("websocket" if _ov_use_ws else "webhook"))
        )
        connection_mode = _coalesce(_ov_cm, top_connection_mode, "websocket")
        webhook_path = _coalesce(
            ov.get("webhookPath") or ov.get("webhook_path"),
            top_webhook_path,
            "/feishu/events",
        )
        webhook_host = _coalesce(
            ov.get("webhookHost") or ov.get("webhook_host"),
            top_webhook_host,
            "127.0.0.1",
        )
        webhook_port = int(_coalesce(
            ov.get("webhookPort") or ov.get("webhook_port"),
            top_webhook_port,
            3000,
        ))

        dm_policy = _coalesce(
            ov.get("dmPolicy") or ov.get("dm_policy"),
            top.get("dmPolicy") or top.get("dm_policy"),
            "pairing",
        )
        allow_from = _str_list(ov.get("allowFrom") or ov.get("allow_from") or
                                top.get("allowFrom") or top.get("allow_from") or [])
        group_policy = _coalesce(
            ov.get("groupPolicy") or ov.get("group_policy"),
            top.get("groupPolicy") or top.get("group_policy"),
            "allowlist",
        )
        group_allow_from = _str_list(
            ov.get("groupAllowFrom") or ov.get("group_allow_from") or
            top.get("groupAllowFrom") or top.get("group_allow_from") or []
        )
        group_sender_allow_from = _str_list(
            ov.get("groupSenderAllowFrom") or ov.get("group_sender_allow_from") or
            top.get("groupSenderAllowFrom") or top.get("group_sender_allow_from") or []
        )
        require_mention = bool(_coalesce(
            ov.get("requireMention") if "requireMention" in ov else None,
            top.get("requireMention") if "requireMention" in top else None,
            True,
        ))
        groups_raw: dict[str, Any] = dict(top.get("groups") or {})
        groups_raw.update(ov.get("groups") or {})
        groups = {
            k: FeishuGroupConfig.from_dict(v or {})
            for k, v in groups_raw.items()
        }

        group_session_scope = _coalesce(
            ov.get("groupSessionScope") or ov.get("group_session_scope"),
            top.get("groupSessionScope") or top.get("group_session_scope"),
            "group",
        )
        topic_session_mode = _coalesce(
            ov.get("topicSessionMode") or ov.get("topic_session_mode"),
            top.get("topicSessionMode") or top.get("topic_session_mode"),
            "disabled",
        )
        reply_in_thread = _coalesce(
            ov.get("replyInThread") or ov.get("reply_in_thread"),
            top.get("replyInThread") or top.get("reply_in_thread"),
            "disabled",
        )

        render_mode = _coalesce(
            ov.get("renderMode") or ov.get("render_mode"),
            top.get("renderMode") or top.get("render_mode"),
            "auto",
        )
        streaming = bool(_coalesce(
            ov.get("streaming"),
            top.get("streaming"),
            True,
        ))
        typing_indicator = bool(_coalesce(
            ov.get("typingIndicator") if "typingIndicator" in ov else None,
            top.get("typingIndicator") if "typingIndicator" in top else None,
            True,
        ))
        resolve_sender_names = bool(_coalesce(
            ov.get("resolveSenderNames") if "resolveSenderNames" in ov else None,
            top.get("resolveSenderNames") if "resolveSenderNames" in top else None,
            True,
        ))
        reaction_notifications = _coalesce(
            ov.get("reactionNotifications") or ov.get("reaction_notifications"),
            top.get("reactionNotifications") or top.get("reaction_notifications"),
            "own",
        )
        text_chunk_limit = int(_coalesce(
            ov.get("textChunkLimit") or ov.get("text_chunk_limit"),
            top.get("textChunkLimit") or top.get("text_chunk_limit"),
            4000,
        ))
        chunk_mode = _coalesce(
            ov.get("chunkMode") or ov.get("chunk_mode"),
            top.get("chunkMode") or top.get("chunk_mode"),
            "length",
        )
        media_max_mb = float(_coalesce(
            ov.get("mediaMaxMb") or ov.get("media_max_mb"),
            top.get("mediaMaxMb") or top.get("media_max_mb"),
            30.0,
        ))
        history_limit = int(_coalesce(
            ov.get("historyLimit") or ov.get("history_limit"),
            top.get("historyLimit") or top.get("history_limit"),
            50,
        ))
        dm_history_limit = int(_coalesce(
            ov.get("dmHistoryLimit") or ov.get("dm_history_limit"),
            top.get("dmHistoryLimit") or top.get("dm_history_limit"),
            0,
        ))
        dms_raw: dict[str, Any] = dict(top.get("dms") or {})
        dms_raw.update(ov.get("dms") or {})
        dms = {k: FeishuDmConfig.from_dict(v or {}) for k, v in dms_raw.items()}

        tools_raw = ov.get("tools") or top.get("tools")
        tools = FeishuToolsConfig.from_dict(tools_raw if isinstance(tools_raw, dict) else None)

        dynamic_raw = ov.get("dynamicAgentCreation") or top.get("dynamicAgentCreation")
        dynamic_agent_creation = DynamicAgentCreationConfig.from_dict(
            dynamic_raw if isinstance(dynamic_raw, dict) else None
        )

        markdown_raw = ov.get("markdown") or top.get("markdown")
        markdown = MarkdownConfig.from_dict(markdown_raw if isinstance(markdown_raw, dict) else None)

        coalesce_raw = ov.get("blockStreamingCoalesce") or top.get("blockStreamingCoalesce")
        block_streaming_coalesce = BlockStreamingCoalesceConfig.from_dict(
            coalesce_raw if isinstance(coalesce_raw, dict) else None
        )

        return ResolvedFeishuAccount(
            account_id=account_id,
            app_id=app_id,
            app_secret=app_secret,
            encrypt_key=(ov.get("encryptKey") or top.get("encryptKey") or "").strip(),
            verification_token=(ov.get("verificationToken") or top.get("verificationToken") or "").strip(),
            domain=domain,
            domain_url=resolve_domain(domain),
            connection_mode=connection_mode,
            webhook_path=webhook_path,
            webhook_host=webhook_host,
            webhook_port=webhook_port,
            dm_policy=dm_policy,
            allow_from=allow_from,
            group_policy=group_policy,
            group_allow_from=group_allow_from,
            group_sender_allow_from=group_sender_allow_from,
            require_mention=require_mention,
            groups=groups,
            group_session_scope=group_session_scope,
            topic_session_mode=topic_session_mode,
            reply_in_thread=reply_in_thread,
            history_limit=history_limit,
            dm_history_limit=dm_history_limit,
            dms=dms,
            render_mode=render_mode,
            streaming=streaming,
            text_chunk_limit=text_chunk_limit,
            chunk_mode=chunk_mode,
            media_max_mb=media_max_mb,
            markdown=markdown,
            block_streaming_coalesce=block_streaming_coalesce,
            typing_indicator=typing_indicator,
            resolve_sender_names=resolve_sender_names,
            reaction_notifications=reaction_notifications,
            tools=tools,
            dynamic_agent_creation=dynamic_agent_creation,
        )

    if accounts_dict:
        # Multi-account mode
        for acct_id, acct_cfg in accounts_dict.items():
            acct = build_account(acct_id, acct_cfg or {})
            if acct is not None:
                results.append(acct)
    else:
        # Single-account mode using top-level credentials
        acct = build_account("default", {})
        if acct is not None:
            results.append(acct)

    return results
