# OpenClaw Python — 使用指南

> 版本 0.8.3 · [English → GUIDE.md](GUIDE.md)

## 目录

1. [快速启动](#快速启动)
2. [安装](#安装)
3. [Telegram 设置](#telegram-设置)
4. [飞书设置](#飞书设置)
5. [权限配置](#权限配置)
6. [往频道发文件](#往频道发文件)
7. [openclaw.json 完整配置参考](#openclaw-json-完整配置参考)
8. [本地模型 Ollama](#本地模型-ollama)
9. [切换 AI 模型](#切换-ai-模型)
10. [Agent 工作区](#agent-工作区)
11. [命令行参考](#命令行参考)

---

## 快速启动

### 第一步：安装依赖

确保已安装 Python 3.11+ 和 `uv` 包管理器。

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

### 第二步：克隆项目

本项目依赖 `pi-mono-python`，两个仓库必须在**同一父目录**下。

```bash
mkdir my-workspace && cd my-workspace
git clone https://github.com/openxjarvis/pi-mono-python.git
git clone https://github.com/openxjarvis/openclaw-python.git
cd openclaw-python
uv sync
```

目录结构应为：

```
my-workspace/
├── openclaw-python/     ← 本项目
└── pi-mono-python/      ← 必须的依赖
```

---

### 第三步：初始化配置

运行向导，交互式填写 API Key、频道配置等。**只需运行一次**（每个新环境）。

```bash
uv run openclaw onboard
```

向导会询问：

- LLM 提供商和 API Key（Gemini / OpenAI / Claude / Ollama）
- 默认模型
- Telegram / 飞书 频道配置
- Gateway 端口（默认 `18789`）
- 工作区和 Agent 人格初始化

> **提示：** 如已有 `.env` 文件，向导会自动检测并复用其中的 Key，无需手动填写。

---

### 第四步：启动

```bash
uv run openclaw start
```

这一条命令启动一切：Gateway 服务器 + 所有已配置的频道（Telegram、飞书等）。

启动成功后日志会显示：

```
✓ Gateway running on ws://127.0.0.1:18789
✓ ChannelManager: 2 channels running
```

然后打开浏览器访问 Web 控制台：`http://localhost:18789`

---

### 第五步：发消息测试

- **Telegram：** 在 Telegram 里找到你的 Bot，发送任意消息
- **飞书：** 在飞书里给 Bot 发私信，首次使用需完成 pairing（见下方配置说明）
- **Web UI：** 直接在 `http://localhost:18789` 的界面聊天

---

### 常见问题

| 问题 | 原因 | 解法 |
|---|---|---|
| 发消息没有反应 | Bot 未配对 | 查看 pairing 章节 |
| 飞书没反应 | App 未启用 Bot 能力或未订阅事件 | 查看飞书配置章节 |
| 端口冲突 | 已有进程占用 18789 | `uv run openclaw cleanup --ports 18789` |
| API Key 无效 | Key 未填或填错 | `uv run openclaw config show` 检查 |
| 每次关终端就停了 | 前台运行模式 | 用 `gateway install` 安装为系统服务 |

---

### 后台运行（可选）

如需开机自启、关闭终端后继续运行：

```bash
# 安装为系统服务（一次性）
uv run openclaw gateway install

# 启动后台服务
uv run openclaw gateway start

# 查看状态
uv run openclaw gateway status

# 查看日志
uv run openclaw gateway logs

# 停止
uv run openclaw gateway stop
```

> **注意：** `gateway install` + `gateway start` 和 `openclaw start` 不能同时使用，否则两个进程会争抢同一端口。

---

## 安装

### 系统要求

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) 包管理器
- （可选）Docker — 用于沙箱隔离执行

### 更新

```bash
cd openclaw-python
git pull
uv sync
uv run openclaw start
```

---

## Telegram 设置

### 1. 创建 Bot

1. 打开 Telegram，搜索 `@BotFather`
2. 发送 `/newbot`，按提示填写名称
3. 复制 token（格式：`123456789:ABCdef...`）

### 2. 配置 Token

通过向导（推荐）：
```bash
uv run openclaw onboard
```

或手动写入配置：
```bash
uv run openclaw config set channels.telegram.botToken "YOUR_BOT_TOKEN"
```

### 3. 启动并测试

```bash
uv run openclaw start
```

在 Telegram 中给 Bot 发消息。

### 4. Pairing（访问控制）

默认策略是 `pairing`：新用户发消息时 Bot 会回复一个配对码，需要通过 CLI 审批。

```bash
# 查看待审批请求
uv run openclaw pairing list telegram

# 审批
uv run openclaw pairing approve telegram <code>
```

**跳过配对（开放模式）：**
```bash
uv run openclaw config set channels.telegram.dmPolicy open
```

### 5. Bot 内命令

| 命令 | 功能 |
|------|------|
| `/reset` | 开启新会话 |
| `/cron` | 查看定时任务 |
| `/help` | 显示帮助 |

---

## 飞书设置

### 1. 创建飞书应用

1. 打开 [open.feishu.cn](https://open.feishu.cn/) → 创建应用 → **企业自建应用**
2. 记录 **App ID** 和 **App Secret**

### 2. 开启 Bot 能力

应用管理 → **添加应用能力** → 选择 **机器人**

### 3. 配置权限

在"权限管理"中开启以下权限：

| 权限（Scope） | 用途 |
|---|---|
| `im:message` | 读取消息（必须）|
| `im:message:send_as_bot` | 发送消息（必须）|
| `im:message.reaction:write` | Typing 指示器（emoji reaction）|
| `im:chat` | 群组管理 |
| `contact:user.id:readonly` | 解析用户 ID |

高级工具还需：
- `bitable:app`, `drive:drive` — 多维表格
- `docx:document`, `wiki:wiki` — 文档 / Wiki
- `calendar:calendar`, `calendar:calendar.event:write` — 日历
- `task:task:write` — 任务

### 4. 订阅消息事件

**关键步骤，缺少此步飞书消息无法送达。**

在"事件与回调" → 事件配置：
- 连接方式选 **长连接（WebSocket）**，无需公网地址
- 添加事件：`im.message.receive_v1`

### 5. 发布应用

版本管理 → 创建版本 → 申请上架 / 直接发布

### 6. 配置 OpenClaw

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

### 7. 启动并配对

```bash
uv run openclaw start
```

给 Bot 发私信，Bot 会回复配对码。然后：

```bash
uv run openclaw pairing list feishu
uv run openclaw pairing approve feishu <code>
```

**跳过配对：**
```json
"dmPolicy": "open"
```

### 飞书工具一览

| 工具 | 功能 |
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

## 权限配置

> **重要：如果 Agent 说"我做不到某件事"，先检查权限配置，不一定是代码 bug。**

OpenClaw 有多层独立的权限控制，分别管理不同能力。

---

### 1. 频道访问控制 — 谁能和 Bot 对话

控制哪些用户可以与 Bot 互动。在 `~/.openclaw/openclaw.json` 中按频道配置：

| 策略 | 行为 |
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

**审批配对请求：**
```bash
uv run openclaw pairing list telegram
uv run openclaw pairing approve telegram <code>
```

---

### 2. Bash 执行权限 — Agent 能运行哪些命令

控制 Agent 是否可以通过 `bash` 工具执行 shell 命令：

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
| `deny`（默认）| Agent **完全不能运行 shell 命令**。文件读写工具仍然可用 |
| `allowlist` | 只允许 `safe_bins` 列表中的程序运行 |
| `full` | Agent 可运行任意命令（推荐在自己机器上使用）|

| `ask` 值 | 效果 |
|---|---|
| `off` | 不询问，直接按 security 规则处理 |
| `on-miss` | 当命令不在白名单时询问用户是否允许 |
| `always` | 每次执行都询问 |

> ⚠️ **注意：`exec.security` 只影响 `bash` 工具，与文件读写工具无关。**
> Agent 始终可以使用 `write_file`、`edit`、`read_file` 等工具操作文件，不受此设置限制。

**常见场景：**

| 场景 | 推荐配置 |
|---|---|
| 个人使用，想要完整功能（生成视频/PPT/脚本等）| `security: "full"` |
| 多人共用，限制可运行的程序 | `security: "allowlist"` + 填写 `safe_bins` |
| 只用文件操作，不需要运行命令 | `security: "deny"`（默认）|

---

### 3. 飞书 API 权限

飞书工具依赖飞书开放平台的 API 权限（Scope）。**如果某个飞书工具报 "Access denied"，说明该 Scope 未开通，需要去飞书开发者后台申请。**

在 [open.feishu.cn](https://open.feishu.cn/) → 你的应用 → 权限管理 中开启：

| 权限（Scope） | 用途 |
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

### 4. 文件写入权限

Agent 通过 `write_file`、`edit` 等内置工具写文件，这些工具**不受** `exec.security` 控制，始终可用。

默认情况下 Agent 可以写入：
- `~/.openclaw/workspace/` 及其子目录（推荐的工作目录）
- 任意用户有权访问的路径（如桌面、Downloads 等）

如需路径隔离，启用 Docker 沙箱（`tools.exec.sandbox`），Agent 只能写入容器内的 `/workspace` 目录。

---

### 权限问题速查表

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

## 往频道发文件

> **如果 Agent 声称发了文件但你没收到，或者说"发不了文件"，这里是完整的排查链路。**

### 文件发送的完整流程

```
Agent 输出文本
  └── 包含 MEDIA: token  ←── 必须有这一行，否则文件永远不发送
        └── 路径解析
              ├── HTTP/HTTPS URL → 直接使用
              ├── 绝对路径存在 → 直接使用
              └── 相对路径/文件名 → 在这些目录里搜索：
                    /tmp/openclaw/
                    ~/.openclaw/media/
                    ~/.openclaw/agents/
                    ~/.openclaw/workspace/
                    ~/.openclaw/sandboxes/
                    {session_workspace}/   ←── 本次对话的工作目录
        └── 实际发送
              ├── 本地文件 → 检查是否存在 → 检查是否超过 50 MB
              └── HTTP URL → 直接转发给 Telegram/飞书 API
```

### 发不了文件的常见原因

#### 原因 1：exec.security = deny（最常见）

`bash` 工具被禁用，Agent **无法运行脚本生成文件**（ffmpeg、python 脚本、pptx 生成器等）。

Agent 可以用 `write_file` 直接写文本内容，但不能调用外部程序。

**解决：** 把 `tools.exec.security` 改为 `full` 或 `allowlist`：
```json
{ "tools": { "exec": { "security": "full" } } }
```

#### 原因 2：Agent 没有输出 MEDIA: token

Agent 可能只说了"我已经生成了文件"，但没有在回复里写 `MEDIA:/path/to/file`。
没有 `MEDIA:` 行，文件永远不会发送，只有文字。

**诊断：** 查看 Agent 的原始回复，确认有没有 `MEDIA:` 开头的行。

#### 原因 3：文件路径不存在

Agent 写了 `MEDIA:/some/path/file.pptx`，但那个路径的文件不存在（可能写入了别的地方）。

系统搜索路径包括：
- `/tmp/openclaw/`
- `~/.openclaw/media/`
- `~/.openclaw/workspace/`
- `{session_workspace}/`（本次对话专属目录）

**解决：** 确认 Agent 写入和 MEDIA: 引用的是同一个路径。最佳实践：Agent 使用 `session workspace` 目录（系统每轮自动注入到 system prompt 里）。

#### 原因 4：文件超过 50 MB（Telegram 限制）

Telegram Bot API 限制单文件最大 50 MB。超过后会报错。

**解决：**
- 压缩文件（降分辨率/码率）
- 上传到网盘，发分享链接
- 通过 Telegram 官方客户端手动发送大文件

#### 原因 5：chat_id 不正确

Agent 不知道当前对话的 Telegram chat_id，发送目标错误或为空。

**解决：** 系统每轮会在 system prompt 里注入 `chat_id`（`## Inbound Meta` 块），Agent 应使用该 ID。如果仍有问题，重启 openclaw 让 session 重新初始化。

### 速查表

| 现象 | 原因 | 解决 |
|------|------|------|
| Agent 说"生成了"但没收到文件 | 没有 MEDIA: token | 要求 Agent 在回复里加 `MEDIA:/path` |
| Agent 说"无法生成文件" | `exec.security: deny` | 改为 `full` 或 `allowlist` |
| 收到错误消息"File not found" | 路径写错或文件未创建 | 检查 Agent 写入路径与 MEDIA: 路径是否一致 |
| 收到错误消息"File too large" | 超过 50 MB | 压缩文件或改用链接 |
| 能收到文字但从不发文件 | `MEDIA:` 格式不对 | 必须是独立一行，格式：`MEDIA:/absolute/path` |

---

## openclaw.json 完整配置参考

配置文件位置：`~/.openclaw/openclaw.json`

查看当前配置：`uv run openclaw config show`
修改某项：`uv run openclaw config set <key> <value>`

---

### `agent` — 默认 Agent 配置

```json
"agent": {
  "model": "google/gemini-2.5-pro-preview",
  "verbose": false,
  "maxHistoryTurns": 50,
  "maxHistoryShare": 0.5
}
```

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `model` | 默认 LLM 模型 ID | — |
| `verbose` | 是否输出详细调试日志 | `false` |
| `maxHistoryTurns` | 保留多少轮历史记录发给模型 | `50` |
| `maxHistoryShare` | 历史记录最多占 context 的比例 | `0.5` |

---

### `gateway` — 服务器设置

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

| 字段 | 说明 | 常用值 |
|------|------|--------|
| `port` | 监听端口 | `18789` |
| `bind` | 绑定地址 | `loopback`（仅本机）/ `0.0.0.0`（公网，需谨慎）|
| `mode` | 部署模式 | `local` |
| `auth.mode` | 认证方式 | `token` / `none` |
| `auth.token` | 访问令牌（mode=token 时必填）| 随机字符串 |
| `enable_web_ui` | 是否开启 Web 控制台 | `true` |

---

### `agents` — 多 Agent 与会话策略

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

| 字段 | 说明 |
|------|------|
| `model.primary` | 主模型 |
| `model.fallbacks` | 主模型失败时按顺序尝试的备用模型列表 |
| `compaction.enabled` | 是否自动压缩历史记录（超出 token 限制时）|
| `compaction.mode` | `safeguard`=保留最近的 / `aggressive`=更激进压缩 |
| `maxConcurrent` | 同时处理的最大并发请求数 |
| `subagents.maxSpawnDepth` | 子 Agent 最大嵌套深度（防止无限递归）|

---

### `channels` — 消息频道

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

| 字段 | 说明 | 可选值 |
|------|------|--------|
| `enabled` | 是否启用 | `true` / `false` |
| `botToken` | BotFather 给的 token | — |
| `dmPolicy` | 私信访问策略 | `pairing`（默认）/ `allowlist` / `open` / `disabled` |
| `groupPolicy` | 群组访问策略 | `allowlist`（默认）/ `open` / `disabled` |
| `streamMode` | 流式输出模式 | `partial`（边生成边发）/ `full`（完整后发）|

#### 飞书

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

| 字段 | 说明 |
|------|------|
| `appId` / `appSecret` | 飞书开放平台的应用凭证 |
| `useWebSocket` | 使用长连接（推荐，无需公网地址）|
| `dmPolicy` | 私信访问策略（同 Telegram）|

---

### `tools` — 工具与执行权限

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
  }
}
```

| 字段 | 说明 | 可选值 |
|------|------|--------|
| `profile` | 工具集 profile | `full`（所有工具）/ `minimal`（精简）|
| `exec.security` | Bash 执行安全模式 | `deny` / `allowlist` / `full` |
| `exec.ask` | 命令不被允许时的行为 | `off` / `on-miss`（询问）/ `always` |
| `exec.ask_fallback` | 用户未响应询问时的处理 | `deny` / `allow` |
| `exec.safe_bins` | allowlist 模式下允许的程序列表 | `["python","ffmpeg","git",...]` |
| `exec.timeout_sec` | bash 命令超时秒数 | `120` |
| `apply_patch.workspace_only` | patch 工具是否只能修改 workspace 内的文件 | `true` / `false` |

> **关键：** `exec.security: "deny"` 是最常见的"Agent 无法生成文件"的原因。如需 Agent 运行脚本（生成 PPT、视频、音频等），改为 `full` 或 `allowlist`。

---

### `session` — 会话隔离策略

```json
"session": {
  "dmScope": "main"
}
```

| `dmScope` 值 | 效果 |
|---|---|
| `main`（默认）| 所有频道（Telegram、飞书）的私信共享同一个 main 会话和记忆 |
| `channel` | 每个频道的私信独立会话（互不影响）|
| `user` | 按用户 ID 隔离会话 |

> **说明：** `dmScope: "main"` 意味着你在 Telegram 说的话和在飞书说的话 Agent 都记得，像同一个对话。改为 `channel` 则两边互不干扰。

---

### `messages` — 消息行为

```json
"messages": {
  "ack_reaction_scope": "group-mentions"
}
```

| 字段 | 说明 | 可选值 |
|------|------|--------|
| `ack_reaction_scope` | 何时用 emoji reaction 表示"已收到" | `all` / `group-mentions` / `none` |

---

### `commands` — 原生命令

```json
"commands": {
  "native": "auto",
  "native_skills": "auto"
}
```

| 字段 | 说明 | 可选值 |
|------|------|--------|
| `native` | 是否注册 `/reset`、`/help` 等原生 Bot 命令 | `auto` / `on` / `off` |
| `native_skills` | 是否将 Skills 注册为 Bot 命令 | `auto` / `on` / `off` |

---

### `hooks` — 内部钩子

```json
"hooks": {
  "internal": { "enabled": true }
}
```

内部钩子用于 Agent 自动注册工作区 hooks（workspace 下的 `hooks/` 目录）。一般不需要修改。

---

### 常用配置片段

**开放访问（个人使用）：**
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

**允许生成文件但限制危险命令：**
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

**多频道独立会话：**
```json
{
  "session": { "dmScope": "channel" }
}
```

**飞书和 Telegram 共享记忆（默认行为）：**
```json
{
  "session": { "dmScope": "main" }
}
```

---

## 本地模型 Ollama

无需外部 API，在本地运行 Llama、DeepSeek、Qwen 等模型。

### 安装 Ollama

```bash
# macOS
brew install ollama
ollama serve

# 下载模型
ollama pull llama3.3
ollama pull deepseek-coder
ollama pull qwen2.5:14b
```

### 配置

```bash
uv run openclaw models set ollama/llama3.3
```

或写入配置 `~/.openclaw/openclaw.json`：
```json
{
  "agent": {
    "model": "ollama/llama3.3",
    "fallbackModels": ["ollama/qwen2.5:14b"]
  }
}
```

> **远程 Ollama：** 在 `.env` 中设置 `OLLAMA_BASE_URL=http://your-server:11434`

---

## 切换 AI 模型

```bash
# 查看当前模型
uv run openclaw models status

# 切换模型
uv run openclaw models set google/gemini-2.5-pro-preview
uv run openclaw models set anthropic/claude-3-5-sonnet
uv run openclaw models set openai/gpt-4o
uv run openclaw models set ollama/llama3.3

# 设置备用模型（主模型失败时自动切换）
uv run openclaw models fallbacks add google/gemini-2.5-flash
```

**常用模型 ID：**

| 模型 | ID |
|------|-----|
| Gemini 2.5 Pro | `google/gemini-2.5-pro-preview` |
| Gemini 2.5 Flash | `google/gemini-2.5-flash` |
| Claude 3.5 Sonnet | `anthropic/claude-3-5-sonnet` |
| GPT-4o | `openai/gpt-4o` |
| Llama 3.3（本地）| `ollama/llama3.3` |
| DeepSeek Coder（本地）| `ollama/deepseek-coder` |

---

## Agent 工作区

所有 Agent 生成的文件保存在 `~/.openclaw/workspace/`，这是 Agent 的专属工作目录，不在项目源码里。

### 目录结构

```
~/.openclaw/
├── openclaw.json           # 主配置文件
├── agents/main/
│   ├── agent/              # API Key profiles（权限 0600）
│   └── sessions/           # 会话记录 (.jsonl)
├── credentials/            # OAuth token、pairing 状态
├── cron/                   # 定时任务定义与执行历史
├── delivery-queue/         # 出站消息预写日志
├── feishu/dedup/           # 飞书消息去重
├── identity/               # 设备身份与 auth token
├── logs/                   # Gateway 日志
├── media/                  # 媒体文件（有 TTL 清理）
├── sandboxes/              # 沙箱工作区（Docker 隔离）
├── telegram/               # Telegram offset 和 sticker 缓存
└── workspace/              # Agent 工作目录
    ├── .git/
    ├── AGENTS.md           # Agent 操作指令
    ├── SOUL.md             # Agent 人格
    └── {session-id}/       # 每次对话的专属子目录
        ├── downloads/      # 要发给用户的文件
        ├── output/         # 生成内容
        └── tmp/            # 临时文件
```

```bash
# 查看实际路径
uv run openclaw directory
```

---

## 命令行参考

所有命令都以 `uv run openclaw` 为前缀。加 `--help` 查看详细选项。

### 核心

| 命令 | 说明 |
|------|------|
| `start` | 启动 Gateway + 所有频道（前台）|
| `onboard` | 首次初始化向导 |
| `doctor` | 系统诊断 |
| `version` | 显示版本 |
| `tui` | 终端交互界面 |
| `cleanup` | 清理端口和僵尸进程 |

### Gateway 管理

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

### 配置

| 命令 | 说明 |
|------|------|
| `config show` | 显示完整配置 |
| `config get <key>` | 获取某个配置项 |
| `config set <key> <value>` | 设置配置项 |
| `config unset <key>` | 删除配置项 |
| `directory` | 显示所有状态目录路径 |

### 模型

| 命令 | 说明 |
|------|------|
| `models status` | 显示当前模型配置 |
| `models set <model>` | 切换默认模型 |
| `models fallbacks list` | 列出备用模型 |
| `models fallbacks add <model>` | 添加备用模型 |
| `models fallbacks remove <model>` | 移除备用模型 |

### 频道与 Pairing

| 命令 | 说明 |
|------|------|
| `channels list` | 列出所有频道 |
| `channels status` | 显示连接状态 |
| `pairing list <channel>` | 列出待审批配对请求 |
| `pairing approve <channel> <code>` | 批准配对 |
| `pairing deny <channel> <code>` | 拒绝配对 |
| `pairing clear <channel>` | 清除所有配对请求 |
| `pairing allowlist <channel>` | 查看白名单 |

### 定时任务

| 命令 | 说明 |
|------|------|
| `cron list` | 列出所有定时任务 |
| `cron add` | 添加定时任务（交互）|
| `cron run <job-id>` | 立即执行某个任务 |
| `cron remove <job-id>` | 删除任务 |
| `cron enable <job-id>` | 启用任务 |
| `cron disable <job-id>` | 禁用任务 |

**示例：**
```bash
# 每天早 9 点发日报
uv run openclaw cron add --name "Morning Briefing" --schedule "0 9 * * *"
```

### Agent 与会话

| 命令 | 说明 |
|------|------|
| `agent run` | 通过 Gateway 运行一次 Agent |
| `message send <channel> <target>` | 向频道发送消息 |
| `memory search <query>` | 搜索 Agent 记忆 |
| `memory rebuild` | 重建记忆索引 |

### 技能与工具

| 命令 | 说明 |
|------|------|
| `skills list` | 列出所有技能 |
| `skills refresh` | 刷新技能缓存 |
| `tools list` | 列出所有工具 |
| `plugins list` | 列出已加载插件 |

### 维护

| 命令 | 说明 |
|------|------|
| `logs tail` | 实时查看日志 |
| `logs clear` | 清空日志文件 |
| `cleanup` | 清理进程和端口 |
| `cleanup --kill-all` | 强制终止所有 openclaw 进程 |
| `cleanup --ports 18789` | 释放指定端口 |
| `system heartbeat` | 触发心跳检查 |
