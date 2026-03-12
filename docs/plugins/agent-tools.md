---
summary: "Write agent tools in a plugin (schemas, optional tools, allowlists)"
read_when:
  - You want to add a new agent tool in a plugin
  - You need to make a tool opt-in via allowlists
title: "Plugin Agent Tools"
---

# Plugin agent tools

OpenClaw plugins can register **agent tools** (JSON‑schema functions) that are exposed
to the LLM during agent runs. Tools can be **required** (always available) or
**optional** (opt‑in).

Agent tools are configured under `tools` in the main config, or per‑agent under
`agents.list[].tools`. The allowlist/denylist policy controls which tools the agent
can call.

## Basic tool

```python
from openclaw.plugin_sdk import empty_plugin_config_schema


def register(api) -> None:
    api.register_tool({
        "name": "my_tool",
        "description": "Do a thing",
        "parameters": {
            "type": "object",
            "properties": {
                "input": {"type": "string"},
            },
            "required": ["input"],
        },
        "execute": lambda _id, params: {
            "content": [{"type": "text", "text": params["input"]}]
        },
    })


plugin = {
    "id": "my-plugin",
    "name": "My Plugin",
    "description": "Example plugin with a tool.",
    "config_schema": empty_plugin_config_schema(),
    "register": register,
}
```

## Optional tool (opt‑in)

Optional tools are **never** auto‑enabled. Users must add them to an agent
allowlist.

```python
def register(api) -> None:
    api.register_tool(
        {
            "name": "workflow_tool",
            "description": "Run a local workflow",
            "parameters": {
                "type": "object",
                "properties": {
                    "pipeline": {"type": "string"},
                },
                "required": ["pipeline"],
            },
            "execute": lambda _id, params: {
                "content": [{"type": "text", "text": params["pipeline"]}]
            },
        },
        opts={"optional": True},
    )
```

Enable optional tools in `agents.list[].tools.allow` (or global `tools.allow`):

```json5
{
  agents: {
    list: [
      {
        id: "main",
        tools: {
          allow: [
            "workflow_tool",  // specific tool name
            "workflow",       // plugin id (enables all tools from that plugin)
            "group:plugins",  // all plugin tools
          ],
        },
      },
    ],
  },
}
```

Other config knobs that affect tool availability:

- Allowlists that only name plugin tools are treated as plugin opt-ins; core tools remain
  enabled unless you also include core tools or groups in the allowlist.
- `tools.profile` / `agents.list[].tools.profile` (base allowlist)
- `tools.byProvider` / `agents.list[].tools.byProvider` (provider‑specific allow/deny)
- `tools.sandbox.tools.*` (sandbox tool policy when sandboxed)

## Async tools

Tools can be async functions:

```python
import asyncio

async def _execute_async(_id, params):
    await asyncio.sleep(0.1)
    return {"content": [{"type": "text", "text": f"done: {params['input']}"}]}


def register(api) -> None:
    api.register_tool({
        "name": "async_tool",
        "description": "An async tool",
        "parameters": {
            "type": "object",
            "properties": {"input": {"type": "string"}},
            "required": ["input"],
        },
        "execute": _execute_async,
    })
```

## Rules + tips

- Tool names must **not** clash with core tool names; conflicting tools are skipped.
- Plugin ids used in allowlists must not clash with core tool names.
- Prefer `optional: True` for tools that trigger side effects or require extra
  binaries/credentials.
