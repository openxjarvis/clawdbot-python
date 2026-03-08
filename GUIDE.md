# OpenClaw Python — User Guide

> Version 0.8.3 · [中文版 → GUIDE_CN.md](GUIDE_CN.md)

## Table of Contents

1. [Quick Start](#quick-start)
2. [Installation](#installation)
3. [Telegram Setup](#telegram-setup)
4. [Feishu Setup](#feishu-setup)
5. [Permissions](#permissions)
6. [Sending Files to Channels](#sending-files-to-channels)
7. [openclaw.json Full Config Reference](#openclaw-json-full-config-reference)
8. [Local Models — Ollama](#local-models--ollama)
9. [Switching Models](#switching-models)
10. [Agent Workspace](#agent-workspace)
11. [CLI Reference](#cli-reference)

---

## Quick Start

### Step 1: Install Dependencies

Make sure Python 3.11+ and `uv` are installed.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

### Step 2: Clone the Repos

This project requires `pi-mono-python`. Both repos must be cloned as **siblings** in the same parent directory.

```bash
mkdir my-workspace && cd my-workspace
git clone https://github.com/openxjarvis/pi-mono-python.git
git clone https://github.com/openxjarvis/openclaw-python.git
cd openclaw-python
uv sync
```

Your directory layout should be:

```
my-workspace/
├── openclaw-python/     ← this repo
└── pi-mono-python/      ← required sibling
```

---

### Step 3: First-Time Setup

Run the interactive wizard to set API keys and channel config. **Run once per environment.**

```bash
uv run openclaw onboard
```

The wizard prompts for:

- LLM provider and API key (Gemini / OpenAI / Claude / Ollama)
- Default model
- Telegram / Feishu channel config
- Gateway port (default `18789`)
- Workspace and agent personality initialization

> **Tip:** If you have an existing `.env`, the wizard detects and reuses keys automatically.

---

### Step 4: Start

```bash
uv run openclaw start
```

This single command starts everything: the Gateway server + all configured channels (Telegram, Feishu, etc.).

On successful startup, you'll see:

```
✓ Gateway running on ws://127.0.0.1:18789
✓ ChannelManager: 2 channels running
```

Then open the Web UI in your browser: `http://localhost:18789`

---

### Step 5: Send a Message

- **Telegram:** Find your bot in Telegram and send any message.
- **Feishu:** Send a DM to the bot. First-time users must complete pairing (see Feishu Setup below).
- **Web UI:** Chat directly at `http://localhost:18789`.

---

### Common Issues

| Issue | Cause | Fix |
|---|---|---|
| No response to messages | Bot not paired | See pairing section |
| Feishu not responding | Bot capability not enabled or event not subscribed | See Feishu Setup |
| Port conflict | 18789 already in use | `uv run openclaw cleanup --ports 18789` |
| Invalid API key | Key missing or wrong | `uv run openclaw config show` to verify |
| Stops when terminal closes | Running in foreground | Install as a system service with `gateway install` |
| Bot stuck / no response after a complex task | Agent run looping or timed out | Send `/stop` in chat (Telegram); runs auto-timeout after 3 minutes |
| Messages queued but never processed | Previous run still active | Send `/stop` or wait for the 3-minute timeout |

---

### Background Daemon (Optional)

To keep running after closing the terminal or on reboot:

```bash
# Install as system service (one-time)
uv run openclaw gateway install

# Start the daemon
uv run openclaw gateway start

# Check status
uv run openclaw gateway status

# Tail logs
uv run openclaw gateway logs

# Stop
uv run openclaw gateway stop
```

> **Note:** Don't run both `openclaw start` (foreground) and `gateway start` (daemon) at the same time — they'll conflict on the same port.

---

## Installation

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- (Optional) Docker — for sandboxed execution

### Updating

```bash
cd openclaw-python
git pull
uv sync
uv run openclaw start
```

---

## Telegram Setup

### 1. Create a Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` and follow the prompts
3. Copy the token (format: `123456789:ABCdef...`)

### 2. Configure Token

Via wizard (recommended):
```bash
uv run openclaw onboard
```

Or set directly:
```bash
uv run openclaw config set channels.telegram.botToken "YOUR_BOT_TOKEN"
```

### 3. Start and Test

```bash
uv run openclaw start
```

Send a message to your bot in Telegram.

### 4. Pairing (Access Control)

Default policy is `pairing`: new users get a pairing code when they first message the bot; approve via CLI:

```bash
# List pending requests
uv run openclaw pairing list telegram

# Approve
uv run openclaw pairing approve telegram <code>
```

**Skip pairing (open mode):**
```bash
uv run openclaw config set channels.telegram.dmPolicy open
```

### 5. Streaming Progress (DMs)

In **private DMs**, the bot sends a separate visible message for each reasoning step before calling a tool, so you can follow what it's doing in real time. In **group chats**, a live preview bubble updates as the agent works, and the final message replaces it seamlessly.

### 6. In-Chat Commands

| Command | Function |
|---------|----------|
| `/reset` | Start a new session |
| `/stop` | Abort the currently running agent task and clear the queue |
| `/queue <mode>` | Change message queue behavior: `interrupt` (new message cancels current), `steer` (inject mid-run), `followup` (queue — default), `collect` |
| `/cron` | View scheduled tasks |
| `/help` | Show help |

> **When to use `/stop`:** If the bot seems stuck or unresponsive after a complex request, `/stop` immediately aborts the running task and lets the next message start fresh. Agent runs also auto-timeout after **3 minutes**.

---

## Feishu Setup

### 1. Create a Feishu App

1. Go to [open.feishu.cn](https://open.feishu.cn/) → Create App → **Enterprise Self-built App**
2. Note down the **App ID** and **App Secret**

### 2. Enable Bot Capability

App Management → **Add App Capability** → Select **Bot**

### 3. Configure Permissions

Enable the following scopes in "Permission Management":

| Scope | Purpose |
|---|---|
| `im:message` | Read messages |
| `im:message:send_as_bot` | Send messages |
| `im:message.reaction:write` | Typing indicator (emoji reaction) |
| `im:chat` | Group management |
| `contact:user.id:readonly` | Resolve user IDs |

For advanced tools:
- `bitable:app`, `drive:drive` — Bitable (spreadsheets)
- `docx:document`, `wiki:wiki` — Docs / Wiki
- `calendar:calendar`, `calendar:calendar.event:write` — Calendar
- `task:task:write` — Tasks

### 4. Subscribe to Message Events

**Critical — without this, Feishu messages won't be delivered.**

In "Event & Callbacks" → Event Config:
- Connection type: **Persistent Connection (WebSocket)** — no public IP needed
- Add event: `im.message.receive_v1`

### 5. Publish the App

Version Management → Create Version → Submit for Release / Publish directly

### 6. Configure OpenClaw

Edit `~/.openclaw/openclaw.json`:

```json
{
  "channels": {
    "feishu": {
      "enabled": true,
      "appId": "cli_XXXXXXXXXXXXXXXX",
      "appSecret": "YOUR_APP_SECRET",
      "useWebSocket": true,
      "dmPolicy": "pairing"
    }
  }
}
```

Or via CLI:
```bash
uv run openclaw config set channels.feishu.appId "cli_XXXXXXXXXXXXXXXX"
uv run openclaw config set channels.feishu.appSecret "YOUR_APP_SECRET"
```

### 7. Start and Pair

```bash
uv run openclaw start
```

Send a DM to your bot. It will reply with a pairing code. Then:

```bash
uv run openclaw pairing list feishu
uv run openclaw pairing approve feishu <code>
```

**Skip pairing:**
```json
"dmPolicy": "open"
```

### Feishu Tools Overview

| Tool | Function |
|---|---|
| `feishu_doc_*` | Feishu Docs — create / read / update |
| `feishu_wiki_*` | Wiki space search and management |
| `feishu_drive_*` | Cloud drive file management |
| `feishu_bitable_*` | Bitable — 11 fine-grained operations |
| `feishu_task_*` | Task management (v2 API) |
| `feishu_calendar_*` | Calendar and events (see note below) |
| `feishu_chat_*` | Group operations |
| `feishu_urgent` | Urgent message push |
| `feishu_reactions` | Message reactions |
| `feishu_perm_*` | Document permissions |

---

## Permissions

> **Important: If the agent says "I can't do X", check permissions first — it's usually a config issue, not a code bug.**

OpenClaw has several independent permission layers, each controlling a different capability.

---

### 1. Channel Access — Who can talk to the bot

Controls which users can interact with the bot. Configured per channel in `~/.openclaw/openclaw.json`:

| Policy | Behavior |
|---|---|
| `pairing` (default) | New users receive a pairing code; must be approved via CLI |
| `allowlist` | Only pre-approved users can interact |
| `open` | Any user can interact — not recommended on public networks |
| `disabled` | All DM access disabled |

```json
{
  "channels": {
    "telegram": { "dmPolicy": "open" },
    "feishu":   { "dmPolicy": "pairing" }
  }
}
```

**Approve pairing:**
```bash
uv run openclaw pairing list telegram
uv run openclaw pairing approve telegram <code>
```

---

### 2. Bash Execution — What shell commands the agent can run

Controls whether the agent can execute shell commands via the `bash` tool:

```json
{
  "tools": {
    "exec": {
      "security": "full",
      "ask": "on-miss",
      "safe_bins": ["python", "ffmpeg", "git", "node", "convert"]
    }
  }
}
```

| `security` value | Effect |
|---|---|
| `deny` (default) | Agent **cannot run any shell commands**. File write tools still work. |
| `allowlist` | Only binaries listed in `safe_bins` are allowed |
| `full` | Agent can run any command — recommended for personal use |

| `ask` value | Effect |
|---|---|
| `off` | No prompting — follow security rules silently |
| `on-miss` | Ask user when a command is not in the allowlist |
| `always` | Ask before every command execution |

> ⚠️ **Note: `exec.security` only affects the `bash` tool. File read/write tools (`write_file`, `edit`, `read_file`) are always available regardless of this setting.**

**Common scenarios:**

| Scenario | Recommended config |
|---|---|
| Personal use — full features (video, PPT, scripts, etc.) | `security: "full"` |
| Shared use — restrict which programs can run | `security: "allowlist"` + fill in `safe_bins` |
| File operations only — no shell commands needed | `security: "deny"` (default) |

---

### 3. Feishu API Scopes

Feishu tools depend on API scopes enabled in the Feishu Developer Console. **If a Feishu tool reports "Access denied", the required scope is not enabled — go to the console and add it.**

Enable at [open.feishu.cn](https://open.feishu.cn/) → Your App → Permission Management:

| Scope | Required for |
|---|---|
| `im:message` | Reading messages (required) |
| `im:message:send_as_bot` | Sending messages (required) |
| `im:message.reaction:write` | Typing indicator (emoji reaction) |
| `im:chat` | Group operations |
| `contact:user.id:readonly` | Resolving user IDs |
| `task:task:write` | Creating / updating tasks |
| `task:task:writeonly` | Write-only tasks (alternative to above) |
| `calendar:calendar.event:write` | Creating calendar events |
| `calendar:calendar` | Reading calendar |
| `bitable:app` | Bitable read / write |
| `docx:document` | Feishu Docs read / write |
| `wiki:wiki` | Wiki read / write |
| `drive:drive` | Cloud drive file access |

> ⚠️ **After enabling new scopes, you must publish a new app version for changes to take effect.** Go to Version Management, create a new version, and publish.

---

### 4. File Write Access

The agent writes files using built-in tools (`write_file`, `edit`). These tools are **not affected** by `exec.security` and are always available.

By default the agent can write to:
- `~/.openclaw/workspace/` and subdirectories (recommended working directory)
- Any path the OS user has permission to write

For path isolation, enable Docker sandbox (`tools.exec.sandbox`) — the agent will be restricted to `/workspace` inside the container.

---

### 5. Permission Presets — Quick Level Switching

Instead of editing individual JSON fields, use the built-in preset system to switch between four pre-defined permission levels in one command.

Each preset covers **all three permission dimensions** — execution, inbound (入站), and outbound (出站):

| # | Preset | exec.security | dmPolicy | groupPolicy | allowWithinProvider | allowAcrossProviders |
|---|---|---|---|---|---|---|
| 1 | **Relaxed** | `full` | `open` | `open` | `true` | `true` |
| 2 | **Trusted** ← **recommended** | `full` | `pairing` | `allowlist` | `true` | `false` |
| 3 | **Standard** | `allowlist` | `pairing` | `allowlist` | `true` | `false` |
| 4 | **Strict** | `deny` | `pairing` | `disabled` | `false` | `false` |

**Why Trusted is the recommended default:** Full agent capability with pairing keeps the bot playable and flexible, while still requiring user approval. Group chats are allowlist-only (not open), and the agent can message other chats within the same channel but not across providers.

**Standard safe_bins:** `python`, `pip`, `uv`, `ffmpeg`, `git`, `node`, `npm`, `convert`

**CLI commands:**

```bash
# Check current level (shows inbound + outbound settings)
uv run openclaw security status

# Interactive menu to switch level
uv run openclaw security preset

# Switch directly (no prompts)
uv run openclaw security preset trusted --yes

# JSON output (for scripting)
uv run openclaw security status --json
```

> Presets apply `exec.security`, `safe_bins`, `dmPolicy`, `groupPolicy`, and `tools.message.crossContext` to all configured channels at once.
> After applying, restart OpenClaw: `uv run openclaw start`

---

### Permission Quick Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Agent says "cannot execute commands" | `exec.security: deny` | Set to `allowlist` or `full` |
| Agent writes files but can't run scripts | `exec.security: deny` blocks bash | Set to `full` or add `python`/`ffmpeg` to `safe_bins` |
| Feishu task tool reports permission error | `task:task:write` not enabled | Enable scope in Feishu console and publish new version |
| Feishu calendar tool fails | `calendar:calendar.event:write` not enabled | Same as above |
| New users get no response | `dmPolicy: pairing` waiting for approval | Run `uv run openclaw pairing approve` or set `dmPolicy: open` |
| Some bash commands work but others fail | `allowlist` mode missing that binary | Add the binary to `safe_bins` |
| All tools stop working | Invalid API key or quota exhausted | `uv run openclaw config show` to check key; verify quota |

---

## Sending Files to Channels

> **If the agent says it sent a file but you didn't receive it, or says "I can't send files", here is the complete diagnostic chain.**

### Complete File Delivery Flow

```
Agent outputs text
  └── Contains a MEDIA: token  ←── Required — without this line, no file is ever sent
        └── _resolve_media_path()  ←── Path resolution
              ├── HTTP/HTTPS URL → used as-is
              ├── Absolute path exists → used as-is
              └── Relative path / filename → searched in these directories:
                    /tmp/openclaw/
                    ~/.openclaw/media/
                    ~/.openclaw/agents/
                    ~/.openclaw/workspace/
                    ~/.openclaw/sandboxes/
                    {session_workspace}/   ←── current conversation's working directory
        └── send_media()  ←── actual delivery
              ├── Local file → check exists → check ≤ 50 MB
              └── HTTP URL → forwarded directly to Telegram / Feishu API
```

### Common Causes of File Delivery Failure

#### Cause 1: exec.security = deny (most common)

The `bash` tool is disabled — the agent **cannot run scripts to generate files** (ffmpeg, Python scripts, pptx generators, etc.).

The agent can use `write_file` to create text content, but cannot invoke external programs.

**Fix:** Set `tools.exec.security` to `full` or `allowlist`:
```json
{ "tools": { "exec": { "security": "full" } } }
```

#### Cause 2: No MEDIA: token in the agent's reply

The agent may have said "I generated the file" but did not include `MEDIA:/path/to/file` in its reply. Without a `MEDIA:` line, the file is never sent — only text is delivered.

**Diagnose:** Check the agent's raw reply for a `MEDIA:` line.

#### Cause 3: File path does not exist

The agent wrote `MEDIA:/some/path/file.pptx` but the file doesn't exist at that path (possibly written elsewhere).

The system searches these directories:
- `/tmp/openclaw/`
- `~/.openclaw/media/`
- `~/.openclaw/workspace/`
- `{session_workspace}/` (per-conversation directory)

**Fix:** Verify the agent's write path and MEDIA: reference point to the same location. Best practice: the agent should use the session workspace directory (automatically injected into the system prompt each turn).

#### Cause 4: File exceeds 50 MB (Telegram limit)

The Telegram Bot API has a 50 MB hard limit per file. `send_media` will raise an error if exceeded.

**Fix:**
- Compress the file (reduce resolution / bitrate)
- Upload to cloud storage and share a link
- Send large files manually via the Telegram desktop/mobile client

#### Cause 5: Missing or incorrect chat_id

The agent doesn't know the Telegram chat_id for the current conversation, causing delivery to the wrong target.

**Fix:** The system injects `chat_id` into the system prompt each turn (in the `## Inbound Meta` block). The agent should use that ID. If the issue persists, restart openclaw to reinitialize the session.

### Quick Reference

| Symptom | Cause | Fix |
|------|------|------|
| Agent says "generated it" but file not received | No MEDIA: token | Ask agent to include `MEDIA:/path` in its reply |
| Agent says "cannot generate files" | `exec.security: deny` | Set to `full` or `allowlist` |
| Error: "File not found" | Wrong path or file was never created | Verify agent write path matches MEDIA: reference |
| Error: "File too large" | Exceeds 50 MB | Compress or share via link |
| Text arrives but files never do | Wrong `MEDIA:` format | Must be a standalone line: `MEDIA:/absolute/path` |

---

## openclaw.json Full Config Reference

Config file location: `~/.openclaw/openclaw.json`

View current config: `uv run openclaw config show`
Modify a field: `uv run openclaw config set <key> <value>`

---

### `agent` — Default agent settings

```json
"agent": {
  "model": "google/gemini-2.5-pro-preview",
  "verbose": false,
  "maxHistoryTurns": 50,
  "maxHistoryShare": 0.5
}
```

| Field | Description | Default |
|------|------|--------|
| `model` | Default LLM model ID | — |
| `verbose` | Enable verbose debug logging | `false` |
| `maxHistoryTurns` | Number of history turns sent to the model | `50` |
| `maxHistoryShare` | Max fraction of context window for history | `0.5` |

---

### `gateway` — Server settings

```json
"gateway": {
  "port": 18789,
  "bind": "loopback",
  "mode": "local",
  "auth": {
    "mode": "token",
    "token": "your-secret-token"
  },
  "enable_web_ui": true
}
```

| Field | Description | Common values |
|------|------|--------|
| `port` | Listening port | `18789` |
| `bind` | Bind address | `loopback` (local only) / `0.0.0.0` (public — use with caution) |
| `mode` | Deployment mode | `local` |
| `auth.mode` | Authentication method | `token` / `none` |
| `auth.token` | Access token (required when mode=token) | random string |
| `enable_web_ui` | Enable Web Control UI | `true` |

---

### `agents` — Multi-agent and session settings

```json
"agents": {
  "defaults": {
    "model": {
      "primary": "google/gemini-2.5-pro-preview",
      "fallbacks": ["google/gemini-2.5-flash"]
    },
    "compaction": {
      "enabled": true,
      "mode": "safeguard",
      "reserveTokens": 16384,
      "keepRecentTokens": 20000
    },
    "maxHistoryTurns": 50,
    "maxConcurrent": 4,
    "subagents": {
      "maxConcurrent": 8,
      "maxSpawnDepth": 1,
      "maxChildrenPerAgent": 5,
      "archiveAfterMinutes": 60
    }
  }
}
```

| Field | Description |
|------|------|
| `model.primary` | Primary model |
| `model.fallbacks` | Fallback models tried in order when the primary fails |
| `compaction.enabled` | Auto-compact history when approaching the token limit |
| `compaction.mode` | `safeguard` = keep recent turns / `aggressive` = more aggressive compression |
| `maxConcurrent` | Maximum concurrent requests handled simultaneously |
| `subagents.maxSpawnDepth` | Max sub-agent nesting depth (prevents infinite recursion) |

---

### `channels` — Messaging channels

#### Telegram

```json
"channels": {
  "telegram": {
    "enabled": true,
    "botToken": "123456:ABC...",
    "dmPolicy": "pairing",
    "groupPolicy": "allowlist",
    "streamMode": "partial"
  }
}
```

| Field | Description | Options |
|------|------|--------|
| `enabled` | Enable this channel | `true` / `false` |
| `botToken` | Token from BotFather | — |
| `dmPolicy` | DM access policy | `pairing` (default) / `allowlist` / `open` / `disabled` |
| `groupPolicy` | Group access policy | `allowlist` (default) / `open` / `disabled` |
| `streamMode` | Streaming output mode | `partial` (stream as generated) / `full` (send after complete) |

#### Feishu

```json
"channels": {
  "feishu": {
    "enabled": true,
    "appId": "cli_XXXXXXXXXXXXXXXX",
    "appSecret": "your-app-secret",
    "useWebSocket": true,
    "dmPolicy": "pairing"
  }
}
```

| Field | Description |
|------|------|
| `appId` / `appSecret` | Feishu Developer Console credentials |
| `useWebSocket` | Use persistent WebSocket connection (recommended — no public IP needed) |
| `dmPolicy` | DM access policy (same as Telegram) |

---

### `tools` — Tool and execution permissions

```json
"tools": {
  "profile": "full",
  "exec": {
    "security": "deny",
    "ask": "on-miss",
    "ask_fallback": "deny",
    "safe_bins": ["python", "git", "ffmpeg", "node"],
    "timeout_sec": 120,
    "apply_patch": {
      "enabled": true,
      "workspace_only": true
    }
  },
  "message": {
    "crossContext": {
      "allowWithinProvider": true,
      "allowAcrossProviders": false
    }
  }
}
```

| Field | Description | Options |
|------|------|--------|
| `profile` | Tool set profile | `full` (all tools) / `minimal` (reduced set) |
| `exec.security` | Bash execution security mode | `deny` / `allowlist` / `full` |
| `exec.ask` | Behavior when a command is not permitted | `off` / `on-miss` (ask) / `always` |
| `exec.ask_fallback` | Action when user doesn't respond to ask | `deny` / `allow` |
| `exec.safe_bins` | Allowed programs in allowlist mode | `["python","ffmpeg","git",...]` |
| `exec.timeout_sec` | Bash command timeout in seconds | `120` |
| `apply_patch.workspace_only` | Restrict patch tool to workspace files only | `true` / `false` |
| `message.crossContext.allowWithinProvider` | Allow agent to send messages to other chats within the same channel (e.g., Telegram → other Telegram chats) | `true` (default) / `false` |
| `message.crossContext.allowAcrossProviders` | Allow agent to send messages to a different channel provider (e.g., Telegram session → Discord) | `false` (default) / `true` |

> **Key:** `exec.security: "deny"` is the most common reason the agent "can't generate files". If you need the agent to run scripts (PPT, video, audio generation), set this to `full` or `allowlist`.

> **Shortcut:** Use `uv run openclaw security preset` to switch all permission settings (including inbound and outbound) at once instead of editing JSON manually. See [Permission Presets](#5-permission-presets--quick-level-switching).

---

### `session` — Session isolation strategy

```json
"session": {
  "dmScope": "per-channel-peer"
}
```

| `dmScope` value | Effect |
|---|---|
| `per-channel-peer` **(default)** | Each `(channel, user)` pair gets its own independent session — natural chat-bot behavior |
| `per-peer` | Sessions isolated by user ID across all channels (Telegram + Feishu share a session for the same user) |
| `per-account-channel-peer` | Sessions isolated by `(account, channel, user)` — useful when running multiple bot accounts |
| `main` | All DMs across all channels share one single session |

> **Tip:** The default `per-channel-peer` means your Telegram conversation and Feishu conversation are fully independent. Set to `per-peer` if you want the agent to remember context across both channels for the same user.

---

### `messages` — Message behavior

```json
"messages": {
  "ack_reaction_scope": "group-mentions"
}
```

| Field | Description | Options |
|------|------|--------|
| `ack_reaction_scope` | When to use emoji reactions as acknowledgement | `all` / `group-mentions` / `none` |

---

### `commands` — Native bot commands

```json
"commands": {
  "native": "auto",
  "native_skills": "auto"
}
```

| Field | Description | Options |
|------|------|--------|
| `native` | Register native bot commands (`/reset`, `/help`, etc.) | `auto` / `on` / `off` |
| `native_skills` | Register skills as bot commands | `auto` / `on` / `off` |

---

### `hooks` — Internal hooks

```json
"hooks": {
  "internal": { "enabled": true }
}
```

Internal hooks let the agent auto-register workspace hooks (from the `hooks/` directory in the workspace). Generally no modification needed.

---

### Common Config Snippets

**Open access (personal use):**
```json
{
  "channels": {
    "telegram": { "dmPolicy": "open" },
    "feishu": { "dmPolicy": "open" }
  },
  "tools": {
    "exec": { "security": "full" }
  }
}
```

**Allow file generation but restrict dangerous commands:**
```json
{
  "tools": {
    "exec": {
      "security": "allowlist",
      "ask": "on-miss",
      "safe_bins": ["python", "ffmpeg", "git", "convert", "magick", "node", "npm"]
    }
  }
}
```

**Independent sessions per channel:**
```json
{
  "session": { "dmScope": "channel" }
}
```

**Shared memory across Feishu and Telegram (default):**
```json
{
  "session": { "dmScope": "main" }
}
```

---

## Local Models — Ollama

Run Llama, DeepSeek, Qwen, and more locally — no external API needed.

### Install Ollama

```bash
# macOS
brew install ollama
ollama serve

# Pull models
ollama pull llama3.3
ollama pull deepseek-coder
ollama pull qwen2.5:14b
```

### Configure

```bash
uv run openclaw models set ollama/llama3.3
```

Or in `~/.openclaw/openclaw.json`:
```json
{
  "agent": {
    "model": "ollama/llama3.3",
    "fallbackModels": ["ollama/qwen2.5:14b"]
  }
}
```

> **Remote Ollama:** Set `OLLAMA_BASE_URL=http://your-server:11434` in `.env`

---

## Switching Models

```bash
# Show current model
uv run openclaw models status

# Switch model
uv run openclaw models set google/gemini-2.5-pro-preview
uv run openclaw models set anthropic/claude-3-5-sonnet
uv run openclaw models set openai/gpt-4o
uv run openclaw models set ollama/llama3.3

# Set fallback (auto-switch when primary fails)
uv run openclaw models fallbacks add google/gemini-2.5-flash
```

**Common Model IDs:**

| Model | ID |
|------|-----|
| Gemini 2.5 Pro | `google/gemini-2.5-pro-preview` |
| Gemini 2.5 Flash | `google/gemini-2.5-flash` |
| Claude 3.5 Sonnet | `anthropic/claude-3-5-sonnet` |
| GPT-4o | `openai/gpt-4o` |
| Llama 3.3 (local) | `ollama/llama3.3` |
| DeepSeek Coder (local) | `ollama/deepseek-coder` |

---

## Agent Workspace

All agent-generated files live in `~/.openclaw/workspace/` — the agent's home directory, never inside the project source.

### Directory Layout

```
~/.openclaw/
├── openclaw.json           # Main config
├── agents/main/
│   ├── agent/              # API key profiles (permissions 0600)
│   └── sessions/           # Session history (.jsonl)
├── credentials/            # OAuth tokens, pairing state
├── cron/                   # Scheduled task definitions and history
├── delivery-queue/         # Outbound message write-ahead log
├── feishu/dedup/           # Feishu message deduplication
├── identity/               # Device identity and auth token
├── logs/                   # Gateway logs
├── media/                  # Media files (TTL-cleaned)
├── sandboxes/              # Sandbox workspace (Docker isolation)
├── telegram/               # Telegram offset and sticker cache
└── workspace/              # Agent working directory
    ├── .git/
    ├── AGENTS.md           # Agent operating instructions
    ├── SOUL.md             # Agent personality
    └── {session-id}/       # Per-conversation subdirectory
        ├── downloads/      # Files to send to user
        ├── output/         # Generated content
        └── tmp/            # Scratch files
```

```bash
# Show actual paths
uv run openclaw directory
```

---

## CLI Reference

All commands are prefixed with `uv run openclaw`. Add `--help` for full options.

### Core

| Command | Description |
|---------|----------|
| `start` | Start Gateway + all channels (foreground) |
| `onboard` | First-time setup wizard |
| `doctor` | System diagnostics |
| `version` | Show version |
| `tui` | Terminal UI |
| `cleanup` | Clean up ports and zombie processes |

### Status

| Command | Description |
|---------|----------|
| `status` | Live overview: gateway latency, channel states (OK/WARN/OFF), sessions, uptime |
| `status --json` | Same data as machine-readable JSON (gateway, agent, channels, sessions) |
| `status --all` | Full diagnosis: config path, agent list, gateway log tail, channel detail |
| `status --deep` | Probe all channels (adds live health check per channel) |
| `status health` | Quick reachability check — gateway uptime, connections, latency |
| `status sessions` | List stored conversation sessions with age, kind, and model |

### Gateway Management

| Command | Description |
|---------|----------|
| `gateway run` | Start Gateway only (foreground) |
| `gateway install` | Install as system service (one-time) |
| `gateway start` | Start background daemon |
| `gateway stop` | Stop background daemon |
| `gateway restart` | Restart background daemon |
| `gateway status` | Check daemon status |
| `gateway logs` | Tail daemon logs |
| `gateway uninstall` | Uninstall system service |

### Configuration

| Command | Description |
|---------|----------|
| `config show` | Display full config |
| `config get <key>` | Get a config value |
| `config set <key> <value>` | Set a config value |
| `config unset <key>` | Delete a config value |
| `directory` | Show all state directory paths |

### Models

| Command | Description |
|---------|----------|
| `models status` | Show current model config |
| `models set <model>` | Switch default model |
| `models fallbacks list` | List fallback models |
| `models fallbacks add <model>` | Add a fallback model |
| `models fallbacks remove <model>` | Remove a fallback model |

### Channels & Pairing

| Command | Description |
|---------|----------|
| `channels list` | List all channels |
| `channels status` | Show connection status |
| `pairing list <channel>` | List pending pairing requests |
| `pairing approve <channel> <code>` | Approve a pairing request |
| `pairing deny <channel> <code>` | Deny a pairing request |
| `pairing clear <channel>` | Clear all pairing requests |
| `pairing allowlist <channel>` | View allowlist |

### Cron

| Command | Description |
|---------|----------|
| `cron list` | List all scheduled tasks |
| `cron add` | Add a task (interactive) |
| `cron run <job-id>` | Run a task immediately |
| `cron remove <job-id>` | Delete a task |
| `cron enable <job-id>` | Enable a task |
| `cron disable <job-id>` | Disable a task |

**Example:**
```bash
# Daily briefing at 9am
uv run openclaw cron add --name "Morning Briefing" --schedule "0 9 * * *"
```

### Agent & Sessions

| Command | Description |
|---------|----------|
| `agent run` | Run agent once via Gateway |
| `message send <channel> <target>` | Send a message to a channel |
| `memory search <query>` | Search agent memory |
| `memory rebuild` | Rebuild memory index |

### Skills & Tools

| Command | Description |
|---------|----------|
| `skills list` | List all skills |
| `skills refresh` | Refresh skill cache |
| `tools list` | List all tools |
| `plugins list` | List loaded plugins |

### Maintenance

| Command | Description |
|---------|----------|
| `logs tail` | Tail logs in real time |
| `logs clear` | Clear log files |
| `cleanup` | Clean up processes and ports |
| `cleanup --kill-all` | Force kill all openclaw processes |
| `cleanup --ports 18789` | Release a specific port |
| `system heartbeat` | Trigger a heartbeat check |
