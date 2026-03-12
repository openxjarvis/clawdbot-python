# Onboarding Kimi Coding 默认模型修复

## 问题描述

用户运行 `onboarding` 流程后，发现两个问题：

1. **Configuration Summary 显示错误的模型**: 仍显示旧的 `moonshot/kimi-k2.5` 模型，而不是期望的 `kimi-coding/k2p5`
2. **API Key 获取地址错误**: 显示 `https://kimi.moonshot.cn/subscription` (不可访问)，而不是正确的 `https://www.kimi.com/code/en`

### 根本原因

#### 问题 1: 模型配置

1. **QuickStart 模式加载旧配置**: 
   - `onboarding.py` 第 173-176 行，QuickStart 模式会使用现有的 `openclaw.json` 作为 base
   - 旧配置中的 `agents.defaults.model` 是 `moonshot/kimi-k2.5`，会一直保留到用户手动选择新模型

2. **缺少自动模型设置**:
   - Kimi Code API 在 QuickStart 模式下应该**自动**设置 `kimi-coding/k2p5`，而不需要用户再次选择
   - 即使 `moonshot.py` auth handler 设置了模型，但在 QuickStart 模式下由于加载了旧配置，设置被覆盖

#### 问题 2: API Key URL

- `moonshot.py` 第 68 行使用了错误的 URL `https://kimi.moonshot.cn/subscription`
- TypeScript 版本使用的是 `https://www.kimi.com/code/en`

## 解决方案

### 修改 1: `openclaw/wizard/auth_handlers/moonshot.py`

#### A. 修复 API Key 获取地址 (第 68 行)

```python
# ❌ 之前 (错误):
print("Get your API key from: https://kimi.moonshot.cn/subscription")

# ✅ 现在 (正确):
print("Get your API key at: https://www.kimi.com/code/en")
```

#### B. 自动设置默认模型 (第 94-111 行)

确保 `kimi-code-api-key` 选择时，自动设置 `kimi-coding/k2p5` 作为默认模型：

```python
# Set default model for Kimi Coding (aligned with TS)
# Kimi Code API uses kimi-coding/k2p5 by default
if set_default_model:
    from ...config.schema import AgentsConfig, AgentDefaults, AgentConfig
    
    if not config.agents:
        config.agents = AgentsConfig()
    if not config.agents.defaults:
        config.agents.defaults = AgentDefaults()
    if not config.agent:
        config.agent = AgentConfig()
    
    # Set kimi-coding/k2p5 as default for Kimi Code API
    if auth_choice == "kimi-code-api-key":
        default_model = "kimi-coding/k2p5"
        config.agents.defaults.model = default_model
        config.agent.model = default_model
        print(f"✓ Default model set to: {default_model}")
```

### 修改 2: `openclaw/wizard/onboarding.py`

在 Step 4.5 (Interactive model selection) 中，为 QuickStart + Kimi Code 添加自动设置逻辑（第 218-234 行）：

```python
# IMPORTANT: For kimi-code-api-key in QuickStart, auto-set model without prompting
if auth_choice == "kimi-code-api-key" and mode == "quickstart":
    # Auto-set kimi-coding/k2p5 for QuickStart + Kimi Code
    if not claw_config.agents:
        from openclaw.config.schema import AgentsConfig
        claw_config.agents = AgentsConfig()
    if not claw_config.agents.defaults:
        from openclaw.config.schema import AgentDefaults
        claw_config.agents.defaults = AgentDefaults()
    if not claw_config.agent:
        from openclaw.config.schema import AgentConfig
        claw_config.agent = AgentConfig()
    
    claw_config.agents.defaults.model = "kimi-coding/k2p5"
    claw_config.agent.model = "kimi-coding/k2p5"
    print(f"\n✓ Auto-selected model: kimi-coding/k2p5 (Kimi Code default)")
    skip_model_selection = True
```

## 修改后的行为

### QuickStart 模式 + Kimi Code API

1. 用户选择 **Kimi Code API** 作为 provider
2. 看到正确的提示: `Get your API key at: https://www.kimi.com/code/en` ✅
3. 输入 API key
4. **自动设置** `model = kimi-coding/k2p5`（无需手动选择）
5. Configuration Summary 会正确显示 `kimi-coding/k2p5` ✅
6. 保存到 `openclaw.json` 后，Gateway 启动时会使用正确的模型

### Advanced 模式 + Kimi Code API

1. 用户选择 **Kimi Code API** 作为 provider
2. 看到正确的提示: `Get your API key at: https://www.kimi.com/code/en` ✅
3. 输入 API key
4. 会进入**交互式模型选择**，但 `kimi-coding/k2p5` 会被标记为 **(recommended)**
5. 用户可以选择其他模型（如 `moonshot/moonshot-v1-8k`）或保持推荐的 `kimi-coding/k2p5`

## 测试方法

### 方法 1: 重新运行 Onboarding

```bash
cd /Users/long/Desktop/XJarvis/openclaw-python
uv run openclaw onboard --flow quickstart --accept-risk
```

**期望结果**:
- ✅ 显示正确的 URL: `Get your API key at: https://www.kimi.com/code/en`
- ✅ Configuration Summary 显示 `Model: kimi-coding/k2p5`
- ✅ `~/.openclaw/openclaw.json` 中 `agents.defaults.model` 和 `agent.model` 都是 `"kimi-coding/k2p5"`

### 方法 2: 验证现有配置 + 重启 Gateway

如果不想重新 onboarding，可以直接重启 Gateway：

```bash
cd /Users/long/Desktop/XJarvis/openclaw-python
./restart_gateway.sh
```

**期望结果**:
- Gateway 启动日志显示 `Model: kimi-coding/k2p5`
- 没有 "No API key found for moonshot" 错误
- Telegram 消息可以正常响应

## 相关文件

- `openclaw/wizard/auth_handlers/moonshot.py` - Kimi Code API 认证处理 (URL + 默认模型)
- `openclaw/wizard/onboarding.py` - 主 onboarding 流程 (QuickStart 自动设置)
- `openclaw/agents/runtime.py` - Provider 路由（AnthropicProvider for kimi-coding）
- `openclaw/agents/pi_stream.py` - 模型解析和 base URL
- `~/.openclaw/openclaw.json` - 用户配置文件
- `~/.openclaw/agents/main/agent/auth-profiles.json` - API key 存储

## TypeScript 对齐状态

- ✅ Kimi Coding 使用 Anthropic Messages API (`AnthropicProvider`)
- ✅ Base URL: `https://api.kimi.com/coding/` (带尾部斜杠)
- ✅ API Key 环境变量: `KIMI_API_KEY` 或 `KIMI_CODE_API_KEY`
- ✅ API Key 获取地址: `https://www.kimi.com/code/en`
- ✅ QuickStart 模式自动设置默认模型
- ✅ 推荐模型: `kimi-coding/k2p5`

## 总结

所有修改已完成，现在 **Onboarding 流程的代码本身** 已正确配置：

1. ✅ **URL 修复**: 显示正确的 API Key 获取地址 `https://www.kimi.com/code/en`
2. ✅ **自动模型设置**: QuickStart 模式下选择 Kimi Code API 会自动使用 `kimi-coding/k2p5` 模型
3. ✅ **完全对齐**: 与 TypeScript 版本的行为完全一致
