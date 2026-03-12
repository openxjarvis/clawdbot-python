---
summary: "Plugin lifecycle hooks: events, contexts, and results"
read_when:
  - Writing plugin hooks to intercept agent lifecycle events
  - Debugging hook execution order or missing events
title: "Plugin Hooks"
---

# Plugin Lifecycle Hooks

Plugins intercept agent lifecycle events using **hooks**. Each hook has a
typed event, context, and optional result.

## Registering hooks

```python
from openclaw.plugins.types import (
    PluginHookLlmOutputEvent,
    PluginHookAgentContext,
)


async def on_llm_output(
    event: PluginHookLlmOutputEvent,
    ctx: PluginHookAgentContext,
) -> None:
    print(f"Model: {event.model}, response: {event.assistant_texts}")


def register(api) -> None:
    api.on("llm_output", on_llm_output)
```

## Hook directory shortcut

Load all hooks from a directory automatically:

```python
from openclaw.plugin_sdk import register_plugin_hooks_from_dir


def register(api) -> None:
    register_plugin_hooks_from_dir(api, "./hooks")
```

Each file in `./hooks/` should export a `register(api)` function.

## Available hooks

### Model / Agent

| Hook | Event type | Context | Result |
|------|-----------|---------|--------|
| `before_model_resolve` | `PluginHookBeforeModelResolveEvent` | `PluginHookAgentContext` | `PluginHookBeforeModelResolveResult` |
| `before_prompt_build` | `PluginHookBeforePromptBuildEvent` | `PluginHookAgentContext` | `PluginHookBeforePromptBuildResult` |
| `before_agent_start` | `PluginHookBeforeAgentStartEvent` | `PluginHookAgentContext` | `PluginHookBeforeAgentStartResult` |
| `llm_input` | `PluginHookLlmInputEvent` | `PluginHookAgentContext` | — |
| `llm_output` | `PluginHookLlmOutputEvent` | `PluginHookAgentContext` | — |
| `agent_end` | `PluginHookAgentEndEvent` | `PluginHookAgentContext` | — |

### Session

| Hook | Event type | Context | Result |
|------|-----------|---------|--------|
| `session_start` | `PluginHookSessionStartEvent` | `PluginHookSessionContext` | — |
| `session_end` | `PluginHookSessionEndEvent` | `PluginHookSessionContext` | — |
| `before_compaction` | `PluginHookBeforeCompactionEvent` | `PluginHookSessionContext` | — |
| `after_compaction` | `PluginHookAfterCompactionEvent` | `PluginHookSessionContext` | — |
| `before_reset` | `PluginHookBeforeResetEvent` | `PluginHookSessionContext` | — |

### Messages

| Hook | Event type | Context | Result |
|------|-----------|---------|--------|
| `message_received` | `PluginHookMessageReceivedEvent` | `PluginHookMessageContext` | — |
| `message_sending` | `PluginHookMessageSendingEvent` | `PluginHookMessageContext` | `PluginHookMessageSendingResult` |
| `message_sent` | `PluginHookMessageSentEvent` | `PluginHookMessageContext` | — |
| `before_message_write` | `PluginHookBeforeMessageWriteEvent` | `PluginHookAgentContext` | `PluginHookBeforeMessageWriteResult` |

### Tools

| Hook | Event type | Context | Result |
|------|-----------|---------|--------|
| `before_tool_call` | `PluginHookBeforeToolCallEvent` | `PluginHookToolContext` | `PluginHookBeforeToolCallResult` |
| `after_tool_call` | `PluginHookAfterToolCallEvent` | `PluginHookToolContext` | — |
| `tool_result_persist` | `PluginHookToolResultPersistEvent` | `PluginHookToolResultPersistContext` | `PluginHookToolResultPersistResult` |

### Gateway

| Hook | Event type | Context | Result |
|------|-----------|---------|--------|
| `gateway_start` | `PluginHookGatewayStartEvent` | `PluginHookGatewayContext` | — |
| `gateway_stop` | `PluginHookGatewayStopEvent` | `PluginHookGatewayContext` | — |

## Modifying results

Some hooks support returning modified data (e.g. `message_sending` can rewrite content
or cancel the outbound message; `before_tool_call` can block a tool call):

```python
from openclaw.plugins.types import (
    PluginHookMessageSendingEvent,
    PluginHookMessageContext,
    PluginHookMessageSendingResult,
)


async def on_message_sending(
    event: PluginHookMessageSendingEvent,
    ctx: PluginHookMessageContext,
) -> PluginHookMessageSendingResult:
    if "badword" in event.content:
        return PluginHookMessageSendingResult(cancel=True)
    return PluginHookMessageSendingResult(content=event.content.upper())
```

## Error handling

Hook errors are **swallowed** (logged as warnings) to avoid breaking the agent loop.
Write defensive hooks.
