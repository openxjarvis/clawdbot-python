---
summary: "OpenClaw Python plugins/extensions: discovery, config, and safety"
read_when:
  - Adding or modifying plugins/extensions
  - Documenting plugin install or load rules
title: "Plugins"
---

# Plugins (Extensions)

## Quick start

A plugin is a **small Python module** that extends OpenClaw with extra features
(channels, tools, hooks, and Gateway RPC).

```bash
# See what's already loaded
openclaw plugins list

# Enable a bundled plugin
openclaw plugins enable memory-lancedb

# Disable a bundled plugin
openclaw plugins disable memory-core
```

Restart the Gateway after enabling/disabling plugins, then configure under
`plugins.entries.<id>.config`.

## Available plugins (bundled)

- **memory-core** — file-backed memory search (enabled by default via `plugins.slots.memory`)
- **memory-lancedb** — LanceDB vector memory with auto-recall/capture
- **telegram** — Telegram bot channel
- **discord** — Discord bot channel
- **slack** — Slack bot channel
- **whatsapp** — WhatsApp channel
- **signal** — Signal channel
- **irc** — IRC channel
- **matrix** — Matrix channel (requires `matrix-nio`)
- **voice-call** — Voice call via Twilio/Telnyx
- **device-pair** — Device pairing with QR codes
- **feishu** — Feishu/Lark channel + tools
- **google-antigravity-auth** — Google Antigravity OAuth (disabled by default)
- **google-gemini-cli-auth** — Gemini CLI OAuth (disabled by default)
- **qwen-portal-auth** — Qwen portal OAuth (disabled by default)
- **copilot-proxy** — VS Code Copilot Proxy bridge (disabled by default)

## Plugin API overview

Plugins export a `plugin` dict with `id`, `name`, `description`, `config_schema`,
and `register`. The `register` function receives a `PluginApi` instance:

```python
from openclaw.plugin_sdk import empty_plugin_config_schema


def register(api) -> None:
    # Register a channel
    api.register_channel(my_channel)

    # Register a tool
    api.register_tool({"name": "my_tool", ...})

    # Register a lifecycle hook
    api.on("llm_output", handle_llm_output)

    # Register a background service
    api.register_service({"id": "my-service", "start": start_fn, "stop": stop_fn})

    # Register a CLI command
    api.register_cli(lambda ctx: ctx.program.command("mycmd").action(run_cmd))

    # Register an auto-reply command (no LLM)
    api.register_command({"name": "mystatus", "description": "Status", "handler": status_fn})

    # Register a gateway RPC method
    api.register_gateway_method("myplugin.status", rpc_handler)

    # Register a model provider
    api.register_provider(my_provider)


plugin = {
    "id": "my-plugin",
    "name": "My Plugin",
    "description": "What this plugin does.",
    "config_schema": empty_plugin_config_schema(),
    "register": register,
}
```

## Discovery & precedence

OpenClaw scans, in order:

1. **Bundled extensions** — `<openclaw-python>/extensions/*` (disabled by default)
2. **Global plugins** — `~/.openclaw/plugins/`
3. **Workspace plugins** — `<workspace>/.openclaw/plugins/`
4. **Config paths** — `plugins.loadPaths` in config

Each plugin must include an `openclaw.plugin.json` in its root.

If multiple plugins resolve to the same id, the first match in the order above
wins.

## Config

```json5
{
  plugins: {
    enabled: true,
    allow: ["voice-call"],
    deny: ["untrusted-plugin"],
    loadPaths: ["~/my-custom-extension/"],
    entries: {
      "voice-call": { enabled: true, config: { provider: "twilio" } },
      "memory-lancedb": {
        enabled: true,
        config: {
          embedding: { apiKey: "sk-proj-...", model: "text-embedding-3-small" },
          autoCapture: true,
          autoRecall: true,
        },
      },
    },
  },
}
```

## Plugin slots (exclusive categories)

Some plugin categories are **exclusive** (only one active at a time):

```json5
{
  plugins: {
    slots: {
      memory: "memory-lancedb",  // or "memory-core" or "none"
    },
  },
}
```

## Plugin hooks

Plugins can register lifecycle hooks:

```python
from openclaw.plugins.types import PluginHookLlmOutputEvent, PluginHookAgentContext

async def on_llm_output(event: PluginHookLlmOutputEvent, ctx: PluginHookAgentContext) -> None:
    print(f"LLM response from {event.model}: {event.assistant_texts}")


def register(api) -> None:
    api.on("llm_output", on_llm_output)
```

Available hook names (20 total):
`before_model_resolve`, `before_prompt_build`, `before_agent_start`, `llm_input`,
`llm_output`, `agent_end`, `before_compaction`, `after_compaction`, `before_reset`,
`message_received`, `message_sending`, `message_sent`, `before_tool_call`,
`after_tool_call`, `tool_result_persist`, `before_message_write`, `session_start`,
`session_end`, `gateway_start`, `gateway_stop`.

Hook directories can be loaded with `register_plugin_hooks_from_dir()`:

```python
from openclaw.plugin_sdk import register_plugin_hooks_from_dir

def register(api) -> None:
    register_plugin_hooks_from_dir(api, "./hooks")
```

## Provider plugins (model auth)

Plugins can register **model provider auth** flows:

```python
from openclaw.plugins.types import ProviderPlugin, ProviderAuthMethod

provider = ProviderPlugin(
    id="acme",
    label="AcmeAI",
    auth=[
        ProviderAuthMethod(
            id="api_key",
            label="API Key",
            kind="api_key",
            run=lambda ctx: ...,
        ),
    ],
)

def register(api) -> None:
    api.register_provider(provider)
```

## Auto-reply commands

Commands that execute **without invoking the AI agent**:

```python
from openclaw.plugins.types import OpenClawPluginCommandDefinition

def status_handler(ctx):
    return {"text": f"Plugin running! Channel: {ctx.channel}"}


def register(api) -> None:
    api.register_command(OpenClawPluginCommandDefinition(
        name="mystatus",
        description="Show plugin status",
        handler=status_handler,
    ))
```

Command names:
- Must start with a letter, contain only letters/numbers/hyphens/underscores.
- Cannot override reserved names (`help`, `status`, `reset`, `new`, etc.).
- Are case-insensitive.
- Duplicate registrations are rejected with a diagnostic error.

## Background services

```python
from openclaw.plugins.types import OpenClawPluginService

async def start_service(ctx):
    api.logger.info("Service started")

async def stop_service(ctx):
    api.logger.info("Service stopped")


def register(api) -> None:
    api.register_service(OpenClawPluginService(
        id="my-service",
        start=start_service,
        stop=stop_service,
    ))
```

## Gateway RPC methods

```python
def register(api) -> None:
    def handle_status(params, respond):
        respond(True, {"ok": True, "status": "running"})

    api.register_gateway_method("myplugin.status", handle_status)
```

## Naming conventions

- Gateway methods: `pluginId.action` (example: `voicecall.status`)
- Tools: `snake_case` (example: `voice_call`)
- CLI commands: kebab or underscore, avoid clashing with core commands

## Safety notes

Plugins run in-process with the Gateway. Treat them as trusted code:

- Only load plugins you trust.
- Prefer `plugins.allow` allowlists.
- Restart the Gateway after changes.
