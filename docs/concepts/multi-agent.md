---
summary: "Multi-agent configuration: multiple named agents on a single gateway"
read_when:
  - Setting up multiple agents with different personas or models
  - Routing channels to specific agents
title: "Multi-Agent"
---

# Multi-Agent

OpenClaw Python supports running **multiple named agents** on a single gateway
instance. Each agent has its own workspace, session store, and configuration.

## Configuration

```json5
{
  agents: {
    defaults: {
      workspace: "~/.openclaw/workspace",
      model: "anthropic/claude-opus-4-5",
    },
    list: [
      {
        id: "main",
        workspace: "~/.openclaw/workspace",
        model: "anthropic/claude-opus-4-5",
      },
      {
        id: "coder",
        workspace: "~/.openclaw/workspace-coder",
        model: "openai/gpt-4o",
        tools: {
          allow: ["group:coding"],
        },
      },
    ],
  },
}
```

## Channel routing

Route specific channels to specific agents:

```json5
{
  channels: {
    telegram: {
      agentId: "main",
    },
    discord: {
      agentId: "coder",
    },
  },
}
```

## Per-agent workspaces

Each agent has its own workspace with separate:
- Bootstrap files (AGENTS.md, SOUL.md, TOOLS.md, etc.)
- Session storage
- Memory files
- Skills

## Agent tools: agent_send

Use the `agent_send` tool to have one agent pass a task to another:

```
Send the code review task to the coder agent.
```

The `agent_send` tool routes the message to the target agent's session queue.

## Notes

- Agents share the same plugin registry (all plugins are available to all agents).
- Each agent can have different model, tools, and skill configurations.
- Session isolation is per-agent: sessions from `main` and `coder` are separate.
