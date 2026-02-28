"""Built-in command definitions.

Fully aligned with TypeScript openclaw/src/auto-reply/commands-registry.data.ts
"""
from __future__ import annotations

from typing import Any


class CommandArg:
    """Command argument definition."""
    
    def __init__(
        self,
        name: str,
        description: str,
        arg_type: str = "string",
        required: bool = False,
        optional: bool = False,
        choices: list[str] | dict[str, str] | None = None,
        capture_remaining: bool = False,
    ):
        self.name = name
        self.description = description
        self.type = arg_type
        self.required = required
        self.optional = optional
        self.choices = choices
        self.capture_remaining = capture_remaining

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


class ChatCommandDefinition:
    """Chat command definition."""
    
    def __init__(
        self,
        key: str,
        description: str,
        native_name: str | None = None,
        text_aliases: list[str] | None = None,
        args: list[CommandArg] | None = None,
        args_parsing: str = "none",
        format_args: Any = None,
        args_menu: str | dict[str, Any] | None = None,
        accepts_args: bool = False,
        scope: str = "both",
        category: str = "general",
    ):
        self.key = key
        self.native_name = native_name
        self.description = description
        self.text_aliases = text_aliases or []
        self.args = args or []
        self.args_parsing = args_parsing
        self.format_args = format_args
        self.args_menu = args_menu
        self.accepts_args = accepts_args or bool(args)
        self.scope = scope
        self.category = category

    @property
    def name(self) -> str | None:
        """Alias for native_name, matching NativeCommandSpec interface."""
        return self.native_name

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)


def _define_chat_command(
    key: str,
    description: str,
    native_name: str | None = None,
    text_alias: str | None = None,
    text_aliases: list[str] | None = None,
    args: list[CommandArg] | None = None,
    args_parsing: str | None = None,
    format_args: Any = None,
    args_menu: str | dict[str, Any] | None = None,
    accepts_args: bool | None = None,
    scope: str | None = None,
    category: str = "general",
) -> ChatCommandDefinition:
    """Define a chat command (mirrors TS defineChatCommand)."""
    aliases = text_aliases or ([text_alias] if text_alias else [])
    aliases = [a.strip() for a in aliases if a and a.strip()]
    
    if scope is None:
        if native_name:
            scope = "both" if aliases else "native"
        else:
            scope = "text"
    
    if accepts_args is None:
        accepts_args = bool(args)
    
    if args_parsing is None:
        args_parsing = "positional" if args else "none"
    
    return ChatCommandDefinition(
        key=key,
        native_name=native_name,
        description=description,
        text_aliases=aliases,
        args=args,
        args_parsing=args_parsing,
        format_args=format_args,
        args_menu=args_menu,
        accepts_args=accepts_args,
        scope=scope,
        category=category,
    )


def _build_chat_commands() -> list[ChatCommandDefinition]:
    """Build the complete command registry (mirrors TS buildChatCommands)."""
    commands = [
        _define_chat_command(
            key="help",
            native_name="help",
            description="Show available commands.",
            text_alias="/help",
            category="status",
        ),
        _define_chat_command(
            key="commands",
            native_name="commands",
            description="List all slash commands.",
            text_alias="/commands",
            category="status",
        ),
        _define_chat_command(
            key="skill",
            native_name="skill",
            description="Run a skill by name.",
            text_alias="/skill",
            category="tools",
            args=[
                CommandArg("name", "Skill name", required=True),
                CommandArg("input", "Skill input", capture_remaining=True),
            ],
        ),
        _define_chat_command(
            key="status",
            native_name="status",
            description="Show current status.",
            text_alias="/status",
            category="status",
        ),
        _define_chat_command(
            key="allowlist",
            description="List/add/remove allowlist entries.",
            text_alias="/allowlist",
            accepts_args=True,
            scope="text",
            category="management",
        ),
        _define_chat_command(
            key="approve",
            native_name="approve",
            description="Approve or deny exec requests.",
            text_alias="/approve",
            accepts_args=True,
            category="management",
        ),
        _define_chat_command(
            key="context",
            native_name="context",
            description="Explain how context is built and used.",
            text_alias="/context",
            accepts_args=True,
            category="status",
        ),
        _define_chat_command(
            key="export-session",
            native_name="export-session",
            description="Export current session to HTML file with full system prompt.",
            text_aliases=["/export-session", "/export"],
            accepts_args=True,
            category="status",
            args=[
                CommandArg("path", "Output path (default: workspace)", required=False),
            ],
        ),
        _define_chat_command(
            key="tts",
            native_name="tts",
            description="Control text-to-speech (TTS).",
            text_alias="/tts",
            category="media",
            args=[
                CommandArg(
                    "action",
                    "TTS action",
                    choices=["on", "off", "status", "provider", "limit", "summary", "audio", "help"],
                ),
                CommandArg("value", "Provider, limit, or text", capture_remaining=True),
            ],
            args_menu={
                "arg": "action",
                "title": (
                    "TTS Actions:\n"
                    "• On – Enable TTS for responses\n"
                    "• Off – Disable TTS\n"
                    "• Status – Show current settings\n"
                    "• Provider – Set voice provider (edge, elevenlabs, openai)\n"
                    "• Limit – Set max characters for TTS\n"
                    "• Summary – Toggle AI summary for long texts\n"
                    "• Audio – Generate TTS from custom text\n"
                    "• Help – Show usage guide"
                ),
            },
        ),
        _define_chat_command(
            key="whoami",
            native_name="whoami",
            description="Show your sender id.",
            text_alias="/whoami",
            category="status",
        ),
        _define_chat_command(
            key="subagents",
            native_name="subagents",
            description="List, kill, log, spawn, or steer subagent runs for this session.",
            text_alias="/subagents",
            category="management",
            args=[
                CommandArg(
                    "action",
                    "list | kill | log | info | send | steer | spawn",
                    choices=["list", "kill", "log", "info", "send", "steer", "spawn"],
                ),
                CommandArg("target", "Run id, index, or session key"),
                CommandArg("value", "Additional input (limit/message)", capture_remaining=True),
            ],
            args_menu="auto",
        ),
        _define_chat_command(
            key="kill",
            native_name="kill",
            description="Kill a running subagent (or all).",
            text_alias="/kill",
            category="management",
            args=[
                CommandArg("target", "Label, run id, index, or all"),
            ],
            args_menu="auto",
        ),
        _define_chat_command(
            key="steer",
            native_name="steer",
            description="Send guidance to a running subagent.",
            text_alias="/steer",
            category="management",
            args=[
                CommandArg("target", "Label, run id, or index"),
                CommandArg("message", "Steering message", capture_remaining=True),
            ],
        ),
        _define_chat_command(
            key="config",
            native_name="config",
            description="Show or set config values.",
            text_alias="/config",
            category="management",
            args=[
                CommandArg("action", "show | get | set | unset", choices=["show", "get", "set", "unset"]),
                CommandArg("path", "Config path"),
                CommandArg("value", "Value for set", capture_remaining=True),
            ],
            args_parsing="none",
        ),
        _define_chat_command(
            key="debug",
            native_name="debug",
            description="Set runtime debug overrides.",
            text_alias="/debug",
            category="management",
            args=[
                CommandArg("action", "show | reset | set | unset", choices=["show", "reset", "set", "unset"]),
                CommandArg("path", "Debug path"),
                CommandArg("value", "Value for set", capture_remaining=True),
            ],
            args_parsing="none",
        ),
        _define_chat_command(
            key="usage",
            native_name="usage",
            description="Usage footer or cost summary.",
            text_alias="/usage",
            category="options",
            args=[
                CommandArg("mode", "off, tokens, full, or cost", choices=["off", "tokens", "full", "cost"]),
            ],
            args_menu="auto",
        ),
        _define_chat_command(
            key="stop",
            native_name="stop",
            description="Stop the current run.",
            text_alias="/stop",
            category="session",
        ),
        _define_chat_command(
            key="restart",
            native_name="restart",
            description="Restart OpenClaw.",
            text_alias="/restart",
            category="tools",
        ),
        _define_chat_command(
            key="activation",
            native_name="activation",
            description="Set group activation mode.",
            text_alias="/activation",
            category="management",
            args=[
                CommandArg("mode", "mention or always", choices=["mention", "always"]),
            ],
            args_menu="auto",
        ),
        _define_chat_command(
            key="send",
            native_name="send",
            description="Set send policy.",
            text_alias="/send",
            category="management",
            args=[
                CommandArg("mode", "on, off, or inherit", choices=["on", "off", "inherit"]),
            ],
            args_menu="auto",
        ),
        _define_chat_command(
            key="reset",
            native_name="reset",
            description="Reset the current session.",
            text_alias="/reset",
            accepts_args=True,
            category="session",
        ),
        _define_chat_command(
            key="new",
            native_name="new",
            description="Start a new session.",
            text_alias="/new",
            accepts_args=True,
            category="session",
        ),
        _define_chat_command(
            key="compact",
            native_name="compact",
            description="Compact the session context.",
            text_alias="/compact",
            category="session",
            args=[
                CommandArg("instructions", "Extra compaction instructions", capture_remaining=True),
            ],
        ),
        _define_chat_command(
            key="think",
            native_name="think",
            description="Set thinking level.",
            text_alias="/think",
            category="options",
            args=[
                CommandArg(
                    "level",
                    "off, minimal, low, medium, high, xhigh",
                    choices=["off", "minimal", "low", "medium", "high", "xhigh"],
                ),
            ],
            args_menu="auto",
        ),
        _define_chat_command(
            key="verbose",
            native_name="verbose",
            description="Toggle verbose mode.",
            text_alias="/verbose",
            category="options",
            args=[
                CommandArg("mode", "on or off", choices=["on", "off"]),
            ],
            args_menu="auto",
        ),
        _define_chat_command(
            key="reasoning",
            native_name="reasoning",
            description="Toggle reasoning visibility.",
            text_alias="/reasoning",
            category="options",
            args=[
                CommandArg("mode", "on, off, or stream", choices=["on", "off", "stream"]),
            ],
            args_menu="auto",
        ),
        _define_chat_command(
            key="elevated",
            native_name="elevated",
            description="Toggle elevated mode.",
            text_alias="/elevated",
            category="options",
            args=[
                CommandArg("mode", "on, off, ask, or full", choices=["on", "off", "ask", "full"]),
            ],
            args_menu="auto",
        ),
        _define_chat_command(
            key="exec",
            native_name="exec",
            description="Set exec defaults for this session.",
            text_alias="/exec",
            category="options",
            args=[
                CommandArg("host", "sandbox, gateway, or node", choices=["sandbox", "gateway", "node"]),
                CommandArg("security", "deny, allowlist, or full", choices=["deny", "allowlist", "full"]),
                CommandArg("ask", "off, on-miss, or always", choices=["off", "on-miss", "always"]),
                CommandArg("node", "Node id or name"),
            ],
            args_parsing="none",
        ),
        _define_chat_command(
            key="model",
            native_name="model",
            description="Show or set the model.",
            text_alias="/model",
            category="options",
            args=[
                CommandArg("model", "Model id (provider/model or id)"),
            ],
        ),
        _define_chat_command(
            key="models",
            native_name="models",
            description="List model providers or provider models.",
            text_alias="/models",
            args_parsing="none",
            accepts_args=True,
            category="options",
        ),
        _define_chat_command(
            key="queue",
            native_name="queue",
            description="Adjust queue settings.",
            text_alias="/queue",
            category="options",
            args=[
                CommandArg(
                    "mode",
                    "queue mode",
                    choices=["steer", "interrupt", "followup", "collect", "steer-backlog"],
                ),
                CommandArg("debounce", "debounce duration (e.g. 500ms, 2s)"),
                CommandArg("cap", "queue cap", arg_type="number"),
                CommandArg("drop", "drop policy", choices=["old", "new", "summarize"]),
            ],
            args_parsing="none",
        ),
        _define_chat_command(
            key="bash",
            description="Run host shell commands (host-only).",
            text_alias="/bash",
            scope="text",
            category="tools",
            args=[
                CommandArg("command", "Shell command", capture_remaining=True),
            ],
        ),
        _define_chat_command(
            key="canvas",
            native_name="canvas",
            description="Present, snapshot, or control the Canvas.",
            text_alias="/canvas",
            category="tools",
            args=[
                CommandArg(
                    "action",
                    "present | snapshot | hide | navigate | eval | status",
                    choices=["present", "snapshot", "hide", "navigate", "eval", "status"],
                ),
                CommandArg("value", "URL or expression (for navigate/eval)", capture_remaining=True),
            ],
            args_parsing="none",
        ),
    ]
    
    # Register additional aliases (mirrors TS registerAlias calls)
    _register_alias(commands, "whoami", "/id")
    _register_alias(commands, "think", "/thinking", "/t")
    _register_alias(commands, "verbose", "/v")
    _register_alias(commands, "reasoning", "/reason")
    _register_alias(commands, "elevated", "/elev")
    _register_alias(commands, "steer", "/tell")

    # Register dock commands for standard channels (mirrors TS listChannelDocks / defineDockCommand)
    for dock_id in ["telegram", "discord", "slack"]:
        commands.append(_define_chat_command(
            key=f"dock:{dock_id}",
            native_name=f"dock_{dock_id}",
            description=f"Switch to {dock_id} for replies.",
            text_aliases=[f"/dock-{dock_id}", f"/dock_{dock_id}"],
            category="docks",
        ))
    
    return commands


def _register_alias(commands: list[ChatCommandDefinition], key: str, *aliases: str) -> None:
    """Register additional aliases for a command."""
    command = next((c for c in commands if c.key == key), None)
    if not command:
        raise ValueError(f"registerAlias: unknown command key: {key}")
    
    existing = {alias.strip().lower() for alias in command.text_aliases}
    
    for alias in aliases:
        trimmed = alias.strip()
        if not trimmed:
            continue
        
        lowered = trimmed.lower()
        if lowered in existing:
            continue
        
        existing.add(lowered)
        command.text_aliases.append(trimmed)


_cached_commands: list[ChatCommandDefinition] | None = None


def get_chat_commands() -> list[ChatCommandDefinition]:
    """Get all chat commands (mirrors TS getChatCommands)."""
    global _cached_commands
    
    if _cached_commands is None:
        _cached_commands = _build_chat_commands()
    
    return _cached_commands


_NATIVE_NAME_PROVIDER_OVERRIDES: dict[str, dict[str, str]] = {
    "discord": {
        "tts": "voice",
    },
}


def list_native_command_specs_for_config(
    cfg: dict[str, Any] | None = None,
    skill_commands: list[Any] | None = None,
    provider: str | None = None,
) -> list[ChatCommandDefinition]:
    """List native command specs (mirrors TS listNativeCommandSpecsForConfig)."""
    cfg = cfg or {}
    commands_cfg = cfg.get("commands", {})
    commands = get_chat_commands()

    result = []
    for c in commands:
        if c.scope not in ("native", "both"):
            continue
        # Filter disabled commands
        if c.key == "config" and not commands_cfg.get("config"):
            continue
        if c.key == "debug" and not commands_cfg.get("debug"):
            continue
        # Apply provider-specific overrides (clone the command if needed)
        if provider and c.key in _NATIVE_NAME_PROVIDER_OVERRIDES.get(provider, {}):
            override_name = _NATIVE_NAME_PROVIDER_OVERRIDES[provider][c.key]
            overridden = ChatCommandDefinition(
                key=c.key,
                native_name=override_name,
                description=c.description,
                text_aliases=list(c.text_aliases),
                args=list(c.args),
                args_parsing=c.args_parsing,
                format_args=c.format_args,
                args_menu=c.args_menu,
                accepts_args=c.accepts_args,
                scope=c.scope,
                category=c.category,
            )
            result.append(overridden)
        else:
            result.append(c)

    # Append skill commands
    if skill_commands:
        for skill_cmd in skill_commands:
            if isinstance(skill_cmd, dict):
                name = skill_cmd.get("name") or skill_cmd.get("skill_name", "")
                description = skill_cmd.get("description", "")
            else:
                name = getattr(skill_cmd, "name", None) or getattr(skill_cmd, "skill_name", "")
                description = getattr(skill_cmd, "description", "")
            if name:
                result.append(_define_chat_command(
                    key=f"skill:{name}",
                    native_name=name,
                    description=description or f"Run {name} skill.",
                    scope="native",
                    category="skills",
                ))

    return result


__all__ = [
    "CommandArg",
    "ChatCommandDefinition",
    "get_chat_commands",
    "list_native_command_specs_for_config",
]
