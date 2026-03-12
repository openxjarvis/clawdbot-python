---
summary: "OpenClaw Python CLI reference"
read_when:
  - Learning the available CLI commands
  - Scripting with the CLI
title: "CLI Reference"
---

# CLI Reference

The `openclaw` CLI manages the gateway and agent configuration.

## Global flags

```
--gateway <url>     WebSocket gateway URL (default: ws://localhost:8080)
--token <token>     Gateway auth token
--agent <id>        Target agent ID (default: main)
--json              Output as JSON
--verbose           Verbose logging
```

## Gateway commands

```bash
openclaw start              # Start the gateway (foreground)
openclaw start --daemon     # Start in background
openclaw stop               # Stop a running gateway
openclaw status             # Show gateway and agent status
openclaw restart            # Restart the gateway
```

## Chat commands

```bash
openclaw chat                  # Interactive REPL with the default agent
openclaw chat --agent coder    # Chat with a specific agent
openclaw send "hello"          # Send a one-off message (non-interactive)
```

## Plugin commands

```bash
openclaw plugins list                  # List all plugins (loaded/disabled)
openclaw plugins enable <id>           # Enable a plugin
openclaw plugins disable <id>          # Disable a plugin
openclaw plugins info <id>             # Show plugin details and config schema
openclaw plugins reload                # Reload all plugins (hot-reload)
```

## Agent / session commands

```bash
openclaw agents list                   # List configured agents
openclaw sessions list                 # List sessions for default agent
openclaw sessions list --agent coder   # Sessions for a specific agent
openclaw sessions reset                # Reset the main session
openclaw sessions reset --session <id> # Reset a specific session
```

## Model commands

```bash
openclaw models list                   # List available models + auth status
openclaw models auth login             # Authenticate with a provider
openclaw models auth logout            # Remove provider credentials
openclaw models auth status            # Check auth status
```

## Memory commands

```bash
openclaw memory list                   # List memory files
openclaw memory search "query"         # Search memory
openclaw memory get <path>             # Get a memory file
openclaw memory clear                  # Clear memory index
```

## Cron commands

```bash
openclaw cron list                     # List configured cron jobs
openclaw cron run <id>                 # Run a cron job immediately
openclaw cron status                   # Show cron scheduler status
```

## Gateway RPC

```bash
openclaw gateway call <method>          # Call a gateway RPC method
openclaw gateway call <method> '{"key": "val"}'  # With JSON payload
```

## Setup

```bash
openclaw setup             # Interactive setup wizard
openclaw config edit       # Open config in $EDITOR
openclaw config validate   # Validate config against schema
openclaw doctor            # Check system health
```

## Environment variables

| Variable | Description |
|----------|-------------|
| `OPENCLAW_GATEWAY` | Gateway WebSocket URL |
| `OPENCLAW_TOKEN` | Gateway auth token |
| `OPENCLAW_CONFIG` | Path to config file |
| `OPENCLAW_WORKSPACE` | Path to workspace |
| `OPENCLAW_LOG_LEVEL` | Log level (debug/info/warning/error) |
