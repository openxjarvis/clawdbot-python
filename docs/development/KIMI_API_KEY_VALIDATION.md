# Kimi Coding API Key 验证报告

**日期**: 2026-03-10  
**状态**: ✅ 完全正常

---

## 测试结果

### 新 API Key 验证

```bash
API Key: sk-kimi-esdLYx355Ac6H2RJWZaIXv1XDS1wCv4Tr8Ef4WvUp2rxsFFlLpCdjFYsv6Bfw01z
状态: ✅ 有效
```

**测试响应**:
```json
{
  "type": "message",
  "role": "assistant",
  "content": [{"type": "text", "text": "Hi there! 👋 How can I help you today?"}],
  "model": "kimi-for-coding",
  "stop_reason": "end_turn",
  "usage": {
    "input_tokens": 0,
    "output_tokens": 15,
    "total_tokens": 15
  }
}
```

---

## Kimi Coding API 关键特性

### 1. API 端点信息

| 配置项 | 值 |
|--------|-----|
| Base URL | `https://api.kimi.com/coding/` |
| Messages 端点 | `/v1/messages` |
| Model ID | `k2p5` (kimi-for-coding) |
| API 类型 | `anthropic-messages` |

### 2. 认证方式

**兼容 Anthropic Messages API 标准**:

```bash
# HTTP Header
x-api-key: YOUR_KIMI_API_KEY
anthropic-version: 2023-06-01
Content-Type: application/json
```

**Python SDK (Anthropic)**:
```python
from anthropic import AsyncAnthropic

client = AsyncAnthropic(
    api_key="sk-kimi-...",
    base_url="https://api.kimi.com/coding/"
)
```

### 3. 模型特性

- **Context Window**: 262,144 tokens (256K)
- **Max Output**: 32,768 tokens
- **Reasoning**: 支持 (adaptive thinking)
- **Input Types**: text, image
- **Streaming**: 支持
- **Tools**: 支持 function calling

---

## TypeScript vs Python 对齐验证

### ✅ 完全对齐的配置

| 配置项 | TypeScript | Python | 状态 |
|--------|-----------|--------|------|
| **Base URL** | `https://api.kimi.com/coding/` | `https://api.kimi.com/coding/` | ✅ 一致 |
| **Model ID** | `k2p5` | `k2p5` | ✅ 一致 |
| **Provider** | `kimi-coding` | `kimi-coding` | ✅ 一致 |
| **API Type** | `anthropic-messages` | `anthropic-messages` | ✅ 一致 |
| **Auth Header** | `x-api-key` | `x-api-key` | ✅ 一致 |
| **Context Window** | 262144 | 262144 | ✅ 一致 |
| **Max Tokens** | 32768 | 32768 | ✅ 一致 |

### TypeScript 实现参考

```typescript
// src/agents/models-config.providers.ts
const KIMI_CODING_BASE_URL = "https://api.kimi.com/coding/";
const KIMI_CODING_DEFAULT_MODEL_ID = "k2p5";

export function buildKimiCodingProvider(): ProviderConfig {
  return {
    baseUrl: KIMI_CODING_BASE_URL,
    api: "anthropic-messages",  // ✅ 关键: 使用 Anthropic Messages API
    models: [{
      id: KIMI_CODING_DEFAULT_MODEL_ID,
      name: "Kimi for Coding",
      reasoning: true,
      input: ["text", "image"],
      contextWindow: 262144,
      maxTokens: 32768,
    }],
  };
}
```

### Python 实现

```python
# openclaw/agents/runtime.py
if provider_name in ("kimi-coding", "kimi"):
    # Kimi Coding API uses Anthropic Messages API format
    kwargs["base_url"] = "https://api.kimi.com/coding/"
    kwargs["api_key"] = os.getenv("KIMI_API_KEY") or os.getenv("KIMI_CODE_API_KEY")
    return AnthropicProvider(provider_name_override="kimi-coding", **kwargs)
```

---

## API 特殊要求总结

### ✅ 必须模仿 Anthropic

Kimi Coding API **完全兼容** Anthropic Messages API:

1. **使用相同的 SDK**: `anthropic` Python SDK / `@anthropic-ai/sdk` TypeScript
2. **相同的 API 格式**: 请求/响应结构与 Anthropic 一致
3. **相同的认证方式**: `x-api-key` header
4. **相同的版本标识**: `anthropic-version: 2023-06-01`
5. **相同的消息格式**: `messages` 数组、`role`、`content` 结构
6. **相同的工具调用**: `tool_use` 和 `tool_result` 格式

### ❌ 不模仿 OpenAI

虽然 Kimi 也提供 OpenAI-compatible 端点 (`https://api.moonshot.ai/v1`)，但 **Kimi Coding API 专门使用 Anthropic 格式**。

---

## 配置文件验证

### ~/.openclaw/openclaw.json
```json
{
  "agent": {
    "model": "kimi-coding/k2p5"
  },
  "agents": {
    "defaults": {
      "model": "kimi-coding/k2p5"
    }
  }
}
```

### ~/.openclaw/agents/main/agent/auth-profiles.json
```json
{
  "profiles": {
    "kimi-coding:default": {
      "type": "api_key",
      "provider": "kimi-coding",
      "key": "sk-kimi-esdLYx355Ac6H2RJWZaIXv1XDS1wCv4Tr8Ef4WvUp2rxsFFlLpCdjFYsv6Bfw01z"
    }
  }
}
```

---

## 问题排查总结

### 问题历史

1. **旧 API Key 失效**
   - Key: `sk-kimi-EeDcQZ4AQhZI...`
   - 错误: `authentication_error`
   - 原因: Key 过期或被撤销

2. **新 API Key 有效**
   - Key: `sk-kimi-esdLYx355Ac6H2RJWZaIXv1XDS1wCv4Tr8Ef4WvUp2rxsFFlLpCdjFYsv6Bfw01z`
   - 状态: ✅ 工作正常

### 代码验证

所有代码实现都是正确的:
- ✅ `openclaw/agents/runtime.py` - AnthropicProvider 使用正确
- ✅ `openclaw/agents/pi_stream.py` - base_url 和 provider 配置正确
- ✅ `openclaw/gateway/pi_runtime.py` - AuthStorage runtime injection 正确
- ✅ `pi-mono-python/packages/ai/src/pi_ai/providers/anthropic.py` - 完全对齐 TS

---

## 下一步操作

### 1. 重启 Gateway 测试

```bash
cd /Users/long/Desktop/XJarvis/openclaw-python

# 停止旧进程
uv run openclaw gateway stop

# 启动新进程
uv run openclaw gateway start
```

### 2. 验证完整流程

```bash
# 测试 chat
uv run openclaw chat

# 或通过 VS Code / Cursor 连接到 ws://127.0.0.1:18789
```

### 3. 可选: 重新 Onboard

如果想完全重置配置:

```bash
# 备份现有配置
cp ~/.openclaw/openclaw.json ~/.openclaw/openclaw.json.backup

# 重新运行 onboarding
uv run openclaw onboard --flow quickstart --accept-risk

# 选择 Kimi Coding API
# 输入新 API key: sk-kimi-esdLYx355Ac6H2RJWZaIXv1XDS1wCv4Tr8Ef4WvUp2rxsFFlLpCdjFYsv6Bfw01z
```

---

## 结论

✅ **所有配置和代码都是正确的！**  
✅ **Python 版本与 TypeScript 版本 100% 对齐！**  
✅ **新 API Key 工作正常！**  
✅ **Kimi Coding API 完全兼容 Anthropic Messages API！**

**问题根源**: 仅仅是旧 API key 过期，与代码无关。
