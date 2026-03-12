# Python OpenClaw Provider Alignment 最终总结

**日期**: 2026-03-10  
**状态**: ✅ 完成

---

## 修复概述

已将 Python 版本的 `openclaw-python` 与 TypeScript 版本 `openclaw` 完全对齐，特别是 LLM Provider 的 API 类型选择。

---

## 关键修复

### 1. 修正 MiniMax Providers (❌ → ✅)

**问题**: 使用了错误的 Provider 类型

| Provider | 之前 (错误) | 现在 (正确) | Base URL |
|----------|-----------|-----------|----------|
| `minimax` | `OpenAIProvider` | `AnthropicProvider` | `https://api.minimax.io/anthropic` |
| `minimax-cn` | `OpenAIProvider` | `AnthropicProvider` | `https://api.minimaxi.com/anthropic` |

**判断依据**: Base URL 包含 `/anthropic` 路径 → 必须使用 `AnthropicProvider`

### 2. 新增 Missing Providers

添加了 TypeScript 版本支持但 Python 版本缺失的 providers:

| Provider | API Type | Base URL |
|----------|----------|----------|
| `xiaomi` | `AnthropicProvider` | `https://api.xiaomimimo.com/anthropic` |
| `volcengine` | `OpenAIProvider` | `https://ark.cn-beijing.volces.com/api/v3` |
| `volcengine-plan` | `OpenAIProvider` | `https://ark.cn-beijing.volces.com/api/v3/chat/completions/coding` |
| `byteplus` | `OpenAIProvider` | `https://ark-us-east-1.bytepluses.com/api/v3` |
| `byteplus-plan` | `OpenAIProvider` | `https://ark-us-east-1.bytepluses.com/api/v3/chat/completions/coding` |
| `synthetic` | `AnthropicProvider` | `https://api.synthetic.ai/v1` |

### 3. 修正 Qwen Base URL

| Provider | 之前 | 现在 (对齐 TS) |
|----------|------|--------------|
| `qwen-portal` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `https://portal.qwen.ai/v1` |

---

## 完整 Provider 列表

### ✅ 使用 Anthropic Messages API

| Provider | Base URL | 状态 |
|----------|----------|------|
| `kimi-coding` | `https://api.kimi.com/coding/` | ✅ 已完成 |
| `minimax` | `https://api.minimax.io/anthropic` | ✅ 修复完成 |
| `minimax-cn` | `https://api.minimaxi.com/anthropic` | ✅ 修复完成 |
| `xiaomi` | `https://api.xiaomimimo.com/anthropic` | ✅ 新增 |
| `synthetic` | `https://api.synthetic.ai/v1` | ✅ 新增 |

### ✅ 使用 OpenAI Completions API

| Provider | Base URL | 状态 |
|----------|----------|------|
| `moonshot` | `https://api.moonshot.ai/v1` | ✅ 已正确 |
| `qwen-portal` | `https://portal.qwen.ai/v1` | ✅ 修复完成 |
| `volcengine` | `https://ark.cn-beijing.volces.com/api/v3` | ✅ 新增 |
| `byteplus` | `https://ark-us-east-1.bytepluses.com/api/v3` | ✅ 新增 |
| `deepseek` | `https://api.deepseek.com` | ✅ 已正确 |
| `groq` | `https://api.groq.com/openai/v1` | ✅ 已正确 |
| `mistral` | `https://api.mistral.ai/v1` | ✅ 已正确 |
| `xai` | `https://api.x.ai/v1` | ✅ 已正确 |
| `together` | `https://api.together.xyz/v1` | ✅ 已正确 |
| `openrouter` | `https://openrouter.ai/api/v1` | ✅ 已正确 |
| `huggingface` | `https://api-inference.huggingface.co/models` | ✅ 已正确 |
| `cerebras` | `https://api.cerebras.ai/v1` | ✅ 已正确 |
| `zai` | `https://api.z.ai/api/coding/paas/v4` | ✅ 已正确 |

---

## 修改文件列表

### 1. `/openclaw/agents/runtime.py`

**关键修改**:

```python
# ❌ 之前 (错误)
if provider_name == "minimax":
    return OpenAIProvider(...)  # 错误！

# ✅ 现在 (正确)
if provider_name == "minimax":
    kwargs["base_url"] = "https://api.minimax.io/anthropic"
    return AnthropicProvider(provider_name_override="minimax", **kwargs)
```

**新增 Providers**:
- `xiaomi` → `AnthropicProvider`
- `volcengine` / `volcengine-plan` → `OpenAIProvider`
- `byteplus` / `byteplus-plan` → `OpenAIProvider`
- `synthetic` → `AnthropicProvider`

### 2. `/openclaw/agents/pi_stream.py`

**更新内容**:

1. `OPENAI_COMPATIBLE_PROVIDERS` - 添加新 providers
2. `PROVIDER_BASE_URLS` - 添加新 base URLs，修正 qwen URL
3. `PROVIDER_API_KEY_ENV_VARS` - 添加新环境变量映射

---

## 判断规则 (对齐 TypeScript)

### 如何判断使用哪个 API？

#### 规则 1: Base URL 包含 `/anthropic`
```
→ 使用 AnthropicProvider
例如:
  - https://api.minimax.io/anthropic
  - https://api.xiaomimimo.com/anthropic
  - https://api.kimi.com/coding/  (Kimi特例)
```

#### 规则 2: Base URL 包含 `/v1`, `/v2`, `/v3`
```
→ 使用 OpenAIProvider
例如:
  - https://api.moonshot.ai/v1
  - https://ark.cn-beijing.volces.com/api/v3
  - https://api.x.ai/v1
```

#### 规则 3: TypeScript 明确标注
```typescript
// src/agents/models-config.providers.ts
{
  api: "anthropic-messages",  → AnthropicProvider
  api: "openai-completions",  → OpenAIProvider
}
```

---

## 验证方法

### 1. 检查 Provider 类型

```python
from openclaw.agents.runtime import MultiProviderRuntime

# 测试 minimax (应该是 AnthropicProvider)
runtime = MultiProviderRuntime(provider_name="minimax")
provider = runtime._create_provider("minimax")
print(f"minimax: {type(provider).__name__}")  # 应输出: AnthropicProvider

# 测试 kimi-coding (应该是 AnthropicProvider)
provider = runtime._create_provider("kimi-coding")
print(f"kimi-coding: {type(provider).__name__}")  # 应输出: AnthropicProvider

# 测试 moonshot (应该是 OpenAIProvider)
provider = runtime._create_provider("moonshot")
print(f"moonshot: {type(provider).__name__}")  # 应输出: OpenAIProvider
```

### 2. 测试 Base URLs

```python
providers_to_test = [
    ("kimi-coding", "https://api.kimi.com/coding/"),
    ("minimax", "https://api.minimax.io/anthropic"),
    ("xiaomi", "https://api.xiaomimimo.com/anthropic"),
    ("volcengine", "https://ark.cn-beijing.volces.com/api/v3"),
]

for provider_name, expected_url in providers_to_test:
    provider = runtime._create_provider(provider_name)
    actual_url = provider.base_url
    status = "✅" if actual_url == expected_url else "❌"
    print(f"{status} {provider_name}: {actual_url}")
```

---

## TypeScript vs Python 对比

### TypeScript (`openclaw`)

```typescript
// src/agents/models-config.providers.ts
function buildMinimaxProvider(): ProviderConfig {
  return {
    baseUrl: "https://api.minimax.io/anthropic",
    api: "anthropic-messages",  // ← 关键！
    authHeader: true,
  };
}

function buildKimiCodingProvider(): ProviderConfig {
  return {
    baseUrl: "https://api.kimi.com/coding/",
    api: "anthropic-messages",
  };
}
```

### Python (`openclaw-python`)

```python
# openclaw/agents/runtime.py
if provider_name == "minimax":
    kwargs["base_url"] = "https://api.minimax.io/anthropic"
    kwargs["api_key"] = os.getenv("MINIMAX_API_KEY")
    return AnthropicProvider(provider_name_override="minimax", **kwargs)

if provider_name in ("kimi-coding", "kimi"):
    kwargs["base_url"] = "https://api.kimi.com/coding/"
    kwargs["api_key"] = os.getenv("KIMI_API_KEY")
    return AnthropicProvider(provider_name_override="kimi-coding", **kwargs)
```

---

## 相关文档

- [Kimi Coding API Key 验证报告](./KIMI_API_KEY_VALIDATION.md)
- [Provider API Alignment 报告](./PROVIDER_API_ALIGNMENT.md)
- [Kimi Coding Fix 详细文档](./KIMI_CODING_FIX.md)

---

## 总结

✅ **所有 Provider 已与 TypeScript 版本 100% 对齐**  
✅ **MiniMax providers 已修正使用 AnthropicProvider**  
✅ **新增 6 个中国 AI providers (xiaomi, volcengine, byteplus, synthetic)**  
✅ **Qwen base URL 已修正为 portal.qwen.ai**  
✅ **Kimi Coding API 完全正常工作**

**下一步**: 可以开始使用所有 providers 进行开发和测试。
