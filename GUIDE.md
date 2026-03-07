# OpenClaw Python — User Guide

> Version 0.8.3

## 目录 / Table of Contents

1. [快速启动 / Quick Start](#快速启动--quick-start)
2. [安装 / Installation](#安装--installation)
3. [Telegram 设置 / Telegram Setup](#telegram-设置--telegram-setup)
4. [飞书设置 / Feishu Setup](#飞书设置--feishu-setup)
5. [权限配置 / Permissions](#权限配置--permissions)
6. [本地模型 Ollama / Local Models](#本地模型-ollama--local-models)
7. [切换 AI 模型 / Switching Models](#切换-ai-模型--switching-models)
8. [Agent 工作区 / Agent Workspace](#agent-工作区--agent-workspace)
9. [命令行参考 / CLI Reference](#命令行参考--cli-reference)

---

## 快速启动 / Quick Start

### 第一步：安装依赖 / Step 1: Install Dependencies

**中文：** 确保已安装 Python 3.11+ 和 `uv` 包管理器。

**English:** Make sure Python 3.11+ and `uv` are installed.

```bash
# 安装 uv / Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

### 第二步：克隆项目 / Step 2: Clone the Repos

**中文：** 本项目依赖 `pi-mono-python`，两个仓库必须在**同一父目录**下。

**English:** This project requires `pi-mono-python`. Both repos must be cloned as **siblings** in the same parent directory.

```bash
mkdir my-workspace && cd my-workspace
git clone https://github.com/openxjarvis/pi-mono-python.git
git clone https://github.com/openxjarvis/openclaw-python.git
cd openclaw-python
uv sync
```

目录结构应为 / Your directory layout should be:

```
my-workspace/
├── openclaw-python/     ← 本项目 / this repo
└── pi-mono-python/      ← 必须的依赖 / required sibling
```

---

### 第三步：初始化配置 / Step 3: First-Time Setup

**中文：** 运行向导，交互式填写 API Key、频道配置等。**只需运行一次**（每个新环境）。

**English:** Run the interactive wizard to set API keys and channel config. **Run once per environment.**

```bash
uv run openclaw onboard
```

向导会询问 / The wizard prompts for:

- LLM 提供商和 API Key（Gemini / OpenAI / Claude / Ollama）
- 默认模型
- Telegram / 飞书 频道配置
- Gateway 端口（默认 `18789`）
- 工作区和 Agent 人格初始化

> **提示：** 如已有 `.env` 文件，向导会自动检测并复用其中的 Key，无需手动填写。
>
> **Tip:** If you have an existing `.env`, the wizard detects and reuses keys automatically.

---

### 第四步：启动 / Step 4: Start

```bash
uv run openclaw start
```

**中文：** 这一条命令启动一切：Gateway 服务器 + 所有已配置的频道（Telegram、飞书等）。

**English:** This single command starts everything: the Gateway server + all configured channels (Telegram, Feishu, etc.).

启动成功后日志会显示 / On successful startup, you'll see:

```
✓ Gateway running on ws://127.0.0.1:18789
✓ ChannelManager: 2 channels running
```

然后打开浏览器访问 Web 控制台 / Then open the Web UI in your browser:

```
http://localhost:18789
```

---

### 第五步：发消息测试 / Step 5: Send a Message

- **Telegram：** 直接在 Telegram 里找到你的 Bot，发送任意消息
- **飞书：** 在飞书里给 Bot 发私信，首次使用需完成 pairing（见下方配置说明）
- **Web UI：** 直接在 `http://localhost:18789` 的界面聊天

---

### 常见问题 / Common Issues

| 问题 / Issue | 原因 / Cause | 解法 / Fix |
|---|---|---|
| 发消息没有反应 | Bot 未配对 / not paired | 查看 pairing 章节 |
| 飞书没反应 | App 未启用 Bot 能力或未订阅事件 | 查看飞书配置章节 |
| 端口冲突 | 已有进程占用 18789 | `uv run openclaw cleanup --ports 18789` |
| API Key 无效 | Key 未填或填错 | `uv run openclaw config show` 检查 |
| 每次关终端就停了 | 前台运行模式 | 用 `gateway install` 安装为系统服务 |

---

### 后台运行（可选）/ Background Daemon (Optional)

**中文：** 如需开机自启、关闭终端后继续运行：

**English:** To keep running after closing the terminal or on reboot:

```bash
# 安装为系统服务（一次性）/ Install as system service (one-time)
uv run openclaw gateway install

# 启动后台服务 / Start the daemon
uv run openclaw gateway start

# 查看状态 / Check status
uv run openclaw gateway status

# 查看日志 / Tail logs
uv run openclaw gateway logs

# 停止 / Stop
uv run openclaw gateway stop
```

> **注意：** `gateway install` + `gateway start` 和 `openclaw start` 不能同时使用，否则两个进程会争抢同一端口。
>
> **Note:** Don't run both `openclaw start` (foreground) and `gateway start` (daemon) at the same time — they'll conflict on the same port.

---

## 安装 / Installation

### 系统要求 / Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) 包管理器
- （可选）Docker — 用于沙箱隔离执行

### 更新 / Updating

```bash
cd openclaw-python
git pull
uv sync
uv run openclaw start
```

---

## Telegram 设置 / Telegram Setup

### 1. 创建 Bot / Create a Bot

1. 打开 Telegram，搜索 `@BotFather`
2. 发送 `/newbot`，按提示填写名称
3. 复制 token（格式：`123456789:ABCdef...`）

### 2. 配置 Token / Configure Token

通过向导（推荐）/ Via wizard (recommended):
```bash
uv run openclaw onboard
```

或手动写入配置 / Or set directly:
```bash
uv run openclaw config set channels.telegram.botToken "YOUR_BOT_TOKEN"
```

### 3. 启动并测试 / Start and Test

```bash
uv run openclaw start
```

在 Telegram 中给 Bot 发消息。

### 4. Pairing（访问控制）/ Pairing (Access Control)

默认策略是 `pairing`：新用户发消息时 Bot 会回复一个配对码，需要通过 CLI 审批。

Default policy is `pairing`: new users get a pairing code when they first message the bot; approve via CLI:

```bash
# 查看待审批请求 / List pending requests
uv run openclaw pairing list telegram

# 审批 / Approve
uv run openclaw pairing approve telegram <code>
```

**跳过配对（开放模式）/ Skip pairing (open mode):**
```bash
uv run openclaw config set channels.telegram.dmPolicy open
```

### 5. Bot 内命令 / In-Chat Commands

| 命令 | 功能 |
|------|------|
| `/reset` | 开启新会话 |
| `/cron` | 查看定时任务 |
| `/help` | 显示帮助 |

---

## 飞书设置 / Feishu Setup

### 1. 创建飞书应用 / Create Feishu App

1. 打开 [open.feishu.cn](https://open.feishu.cn/) → 创建应用 → **企业自建应用**
2. 记录 **App ID** 和 **App Secret**

### 2. 开启 Bot 能力 / Enable Bot Capability

应用管理 → **添加应用能力** → 选择 **机器人**

### 3. 配置权限 / Configure Permissions

在"权限管理"中开启以下权限：

| 权限 / Scope | 用途 / Purpose |
|---|---|
| `im:message` | 读取消息 |
| `im:message:send_as_bot` | 发送消息 |
| `im:message.reaction:write` | Typing 指示器（emoji reaction）|
| `im:chat` | 群组管理 |
| `contact:user.id:readonly` | 解析用户 ID |

高级工具还需 / For advanced tools:
- `bitable:app`, `drive:drive` — 多维表格 / Bitable
- `docx:document`, `wiki:wiki` — 文档 / Docs
- `calendar:calendar`, `calendar:calendar.event` — 日历
- `task:task` — 任务

### 4. 订阅消息事件 / Subscribe to Events

**关键步骤，缺少此步飞书消息无法送达。**

**Critical — without this, Feishu messages won't be delivered.**

在"事件与回调" → 事件配置：
- 连接方式选 **长连接（WebSocket）**，无需公网地址
- 添加事件：`im.message.receive_v1`

### 5. 发布应用 / Publish the App

版本管理 → 创建版本 → 申请上架 / 直接发布

### 6. 配置 OpenClaw / Configure OpenClaw

编辑 `~/.openclaw/openclaw.json`：

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

或通过 CLI：
```bash
uv run openclaw config set channels.feishu.appId "cli_XXXXXXXXXXXXXXXX"
uv run openclaw config set channels.feishu.appSecret "YOUR_APP_SECRET"
```

### 7. 启动并配对 / Start and Pair

```bash
uv run openclaw start
```

给 Bot 发私信，Bot 会回复配对码。然后：

```bash
uv run openclaw pairing list feishu
uv run openclaw pairing approve feishu <code>
```

**跳过配对 / Skip pairing:**
```json
"dmPolicy": "open"
```

### 飞书工具一览 / Feishu Tools

| 工具 / Tool | 功能 / Function |
|---|---|
| `feishu_doc_*` | 飞书文档 创建/读取/更新 |
| `feishu_wiki_*` | Wiki 空间搜索与管理 |
| `feishu_drive_*` | 云空间文件管理 |
| `feishu_bitable_*` | 多维表格（11 个精细操作）|
| `feishu_task_*` | 任务管理（v2 API）|
| `feishu_calendar_*` | 日历与日程 |
| `feishu_chat_*` | 群组操作 |
| `feishu_urgent` | 加急消息 |
| `feishu_reactions` | 消息表情 |
| `feishu_perm_*` | 文档权限 |

---

## 权限配置 / Permissions

> **重要：如果 Agent 说"我做不到某件事"，先检查权限配置，不一定是代码 bug。**
>
> **Important: If the agent says "I can't do X", check permissions first — it's usually a config issue, not a code bug.**

OpenClaw 有多层独立的权限控制，分别管理不同能力：

---

### 1. 频道访问控制 / Channel Access — 谁能和 Bot 对话

控制哪些用户可以与 Bot 互动。在 `~/.openclaw/openclaw.json` 中按频道配置：

| 策略 / Policy | 行为 / Behavior |
|---|---|
| `pairing`（默认）| 新用户首次发消息后收到配对码，需通过 CLI 手动审批 |
| `allowlist` | 只有预先加入白名单的用户才能对话 |
| `open` | 任何人都能直接对话（不推荐在公网使用）|
| `disabled` | 关闭所有私信访问 |

```json
{
  "channels": {
    "telegram": { "dmPolicy": "open" },
    "feishu":   { "dmPolicy": "pairing" }
  }
}
```

**审批配对请求 / Approve pairing:**
```bash
uv run openclaw pairing list telegram
uv run openclaw pairing approve telegram <code>
```

---

### 2. Bash 执行权限 / Bash Execution — Agent 能运行哪些命令

控制 Agent 是否可以通过 `bash` 工具执行 shell 命令。在 `~/.openclaw/openclaw.json` 中配置：

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

| `security` 值 | 效果 |
|---|---|
| `deny`（默认）| Agent **完全不能运行 shell 命令**。适合只用文件操作的场景 |
| `allowlist` | 只允许 `safe_bins` 列表中的程序运行 |
| `full` | Agent 可运行任意命令（推荐在自己机器上使用）|

| `ask` 值 | 效果 |
|---|---|
| `off` | 不询问，直接按 security 规则处理 |
| `on-miss` | 当命令不在白名单时询问用户是否允许 |
| `always` | 每次执行都询问 |

> ⚠️ **注意：`exec.security` 只影响 `bash` 工具，与文件读写工具无关。**
> Agent 始终可以使用 `write_file`、`edit`、`read_file` 等工具操作文件，不受此设置限制。

**常见场景 / Common scenarios:**

| 场景 | 推荐配置 |
|---|---|
| 个人使用，想要完整功能（生成视频/PPT/脚本等）| `security: "full"` |
| 多人共用，限制可运行的程序 | `security: "allowlist"` + 填写 `safe_bins` |
| 只用文件操作，不需要运行命令 | `security: "deny"`（默认）|

---

### 3. 飞书 API 权限 / Feishu App Scopes

飞书工具依赖飞书开放平台的 API 权限（Scope）。**如果某个飞书工具报 "Access denied"，说明该 Scope 未开通，需要去飞书开发者后台申请。**

在 [open.feishu.cn](https://open.feishu.cn/) → 你的应用 → 权限管理 中开启：

| 权限 / Scope | 用途 |
|---|---|
| `im:message` | 读取消息（必须）|
| `im:message:send_as_bot` | 发送消息（必须）|
| `im:message.reaction:write` | Typing 动效（emoji reaction）|
| `im:chat` | 群组操作 |
| `contact:user.id:readonly` | 解析用户 ID |
| `task:task:write` | 创建/更新任务 |
| `task:task:writeonly` | 仅写入任务（task:task:write 的替代）|
| `calendar:calendar.event:write` | 创建日历事件 |
| `calendar:calendar` | 读取日历 |
| `bitable:app` | 多维表格读写 |
| `docx:document` | 飞书文档读写 |
| `wiki:wiki` | Wiki 读写 |
| `drive:drive` | 云空间文件管理 |

> ⚠️ **开通权限后必须发布新版本应用才能生效。**
> 在"版本管理"中创建新版本并发布，否则权限变更不会生效。

---

### 4. 文件写入权限 / File Write Access

Agent 通过 `write_file`、`edit` 等内置工具写文件，这些工具**不受** `exec.security` 控制，始终可用。

默认情况下 Agent 可以写入：
- `~/.openclaw/workspace/` 及其子目录（推荐的工作目录）
- 任意用户有权访问的路径（如桌面、Downloads 等）

如需路径隔离，启用 Docker 沙箱（`tools.exec.sandbox`），Agent 只能写入容器内的 `/workspace` 目录。

---

### 权限问题速查表 / Quick Troubleshooting

| 现象 | 原因 | 解决方法 |
|---|---|---|
| Agent 说"无法执行命令" | `exec.security: deny` | 改为 `allowlist` 或 `full` |
| Agent 能写文件但不能运行脚本生成视频/PPT | `exec.security: deny` 阻止了 bash | 改为 `full` 或添加 `python`/`ffmpeg` 到 `safe_bins` |
| 飞书任务工具报权限错误 | `task:task:write` 未开通 | 飞书控制台开启权限并发布新版本 |
| 飞书日历工具失败 | `calendar:calendar.event:write` 未开通 | 同上 |
| 新用户发消息没反应 | `dmPolicy: pairing` 等待审批 | `uv run openclaw pairing approve` 或改为 `open` |
| Agent 运行了部分命令但某些命令报错 | `allowlist` 模式缺少该二进制 | 把对应程序加入 `safe_bins` |
| 所有工具都不工作 | API Key 无效或 Quota 耗尽 | `uv run openclaw config show` 检查 Key，确认配额 |

---

## 本地模型 Ollama / Local Models

**中文：** 无需外部 API，在本地运行 Llama、DeepSeek、Qwen 等模型。

**English:** Run Llama, DeepSeek, Qwen, and more locally — no external API needed.

### 安装 Ollama / Install Ollama

```bash
# macOS
brew install ollama
ollama serve

# 下载模型 / Pull models
ollama pull llama3.3
ollama pull deepseek-coder
ollama pull qwen2.5:14b
```

### 配置 / Configure

```bash
uv run openclaw models set ollama/llama3.3
```

或写入配置 / Or in `~/.openclaw/openclaw.json`:
```json
{
  "agent": {
    "model": "ollama/llama3.3",
    "fallbackModels": ["ollama/qwen2.5:14b"]
  }
}
```

> **远程 Ollama / Remote Ollama:** 在 `.env` 中设置 `OLLAMA_BASE_URL=http://your-server:11434`

---

## 切换 AI 模型 / Switching Models

```bash
# 查看当前模型 / Show current model
uv run openclaw models status

# 切换模型 / Switch model
uv run openclaw models set google/gemini-2.5-pro-preview
uv run openclaw models set anthropic/claude-opus-4-5
uv run openclaw models set openai/gpt-4o
uv run openclaw models set ollama/llama3.3

# 设置备用模型（主模型失败时自动切换）/ Set fallback
uv run openclaw models fallbacks add google/gemini-2.5-flash
```

**常用模型 ID / Common Model IDs:**

| 模型 | ID |
|------|-----|
| Gemini 2.5 Pro | `google/gemini-2.5-pro-preview` |
| Gemini Flash | `google/gemini-2.5-flash` |
| Claude Opus 4.5 | `anthropic/claude-opus-4-5` |
| GPT-4o | `openai/gpt-4o` |
| Llama 3.3 (本地) | `ollama/llama3.3` |
| DeepSeek Coder (本地) | `ollama/deepseek-coder` |

---

## Agent 工作区 / Agent Workspace

所有 Agent 生成的文件保存在 `~/.openclaw/workspace/`，这是 Agent 的专属工作目录，类似用户的 home 文件夹。

All agent-generated files live in `~/.openclaw/workspace/` — the agent's home directory, never inside the project source.

### 目录结构 / Directory Layout

```
~/.openclaw/
├── openclaw.json           # 主配置文件 / Main config
├── agents/main/
│   ├── agent/              # API Key profiles（权限 0600）
│   └── sessions/           # 会话记录 (.jsonl)
├── credentials/            # OAuth token、pairing 状态
├── cron/                   # 定时任务定义与执行历史
├── delivery-queue/         # 出站消息预写日志
├── feishu/dedup/           # 飞书消息去重
├── identity/               # 设备身份与 auth token
├── logs/                   # Gateway 日志
├── media/                  # 媒体文件
├── sandboxes/              # 沙箱工作区（Docker 隔离）
├── telegram/               # Telegram offset 和 sticker 缓存
└── workspace/              # Agent 工作目录（共享，flat）
    ├── .git/
    ├── AGENTS.md           # Agent 操作指令
    ├── SOUL.md             # Agent 人格
    └── (agent files...)
```

```bash
# 查看实际路径 / Show actual paths
uv run openclaw directory
```

---

## 命令行参考 / CLI Reference

所有命令都以 `uv run openclaw` 为前缀。加 `--help` 查看详细选项。

All commands are prefixed with `uv run openclaw`. Add `--help` for full options.

### 核心 / Core

| 命令 | 说明 |
|------|------|
| `start` | 启动 Gateway + 所有频道（前台）|
| `onboard` | 首次初始化向导 |
| `doctor` | 系统诊断 |
| `version` | 显示版本 |
| `tui` | 终端交互界面 |
| `cleanup` | 清理端口和僵尸进程 |

### Gateway 管理 / Gateway Management

| 命令 | 说明 |
|------|------|
| `gateway run` | 仅启动 Gateway（前台）|
| `gateway install` | 安装为系统服务（一次性）|
| `gateway start` | 启动后台服务 |
| `gateway stop` | 停止后台服务 |
| `gateway restart` | 重启后台服务 |
| `gateway status` | 查看后台服务状态 |
| `gateway logs` | 查看日志 |
| `gateway uninstall` | 卸载系统服务 |

### 配置 / Configuration

| 命令 | 说明 |
|------|------|
| `config show` | 显示完整配置 |
| `config get <key>` | 获取某个配置项 |
| `config set <key> <value>` | 设置配置项 |
| `config unset <key>` | 删除配置项 |
| `directory` | 显示所有状态目录路径 |

### 模型 / Models

| 命令 | 说明 |
|------|------|
| `models status` | 显示当前模型配置 |
| `models set <model>` | 切换默认模型 |
| `models fallbacks list` | 列出备用模型 |
| `models fallbacks add <model>` | 添加备用模型 |
| `models fallbacks remove <model>` | 移除备用模型 |

### 频道与 Pairing / Channels & Pairing

| 命令 | 说明 |
|------|------|
| `channels list` | 列出所有频道 |
| `channels status` | 显示连接状态 |
| `pairing list <channel>` | 列出待审批配对请求 |
| `pairing approve <channel> <code>` | 批准配对 |
| `pairing deny <channel> <code>` | 拒绝配对 |
| `pairing clear <channel>` | 清除所有配对请求 |
| `pairing allowlist <channel>` | 查看白名单 |

### 定时任务 / Cron

| 命令 | 说明 |
|------|------|
| `cron list` | 列出所有定时任务 |
| `cron add` | 添加定时任务（交互）|
| `cron run <job-id>` | 立即执行某个任务 |
| `cron remove <job-id>` | 删除任务 |
| `cron enable <job-id>` | 启用任务 |
| `cron disable <job-id>` | 禁用任务 |

**示例 / Example:**
```bash
# 每天早 9 点发日报 / Daily briefing at 9am
uv run openclaw cron add --name "Morning Briefing" --schedule "0 9 * * *"
```

### Agent 与会话 / Agent & Sessions

| 命令 | 说明 |
|------|------|
| `agent run` | 通过 Gateway 运行一次 Agent |
| `message send <channel> <target>` | 向频道发送消息 |
| `memory search <query>` | 搜索 Agent 记忆 |
| `memory rebuild` | 重建记忆索引 |

### 技能与工具 / Skills & Tools

| 命令 | 说明 |
|------|------|
| `skills list` | 列出所有技能 |
| `skills refresh` | 刷新技能缓存 |
| `tools list` | 列出所有工具 |
| `plugins list` | 列出已加载插件 |

### 维护 / Maintenance

| 命令 | 说明 |
|------|------|
| `logs tail` | 实时查看日志 |
| `logs clear` | 清空日志文件 |
| `cleanup` | 清理进程和端口 |
| `cleanup --kill-all` | 强制终止所有 openclaw 进程 |
| `cleanup --ports 18789` | 释放指定端口 |
| `system heartbeat` | 触发心跳检查 |
