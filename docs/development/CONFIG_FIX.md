# 问题诊断和修复说明

## 问题 1: Skills 没有显示多选安装界面 ✅

### 症状
```
? Configure skills now? (recommended) Yes
✅ Skills setup complete. Installed: 0
```
看起来跳过了多选界面。

### 诊断结果
**这是正确的行为！**

从终端输出：
```
Skills status
-------------
Eligible: 64          ← 64 个 skills 已经满足所有依赖
Missing requirements: 0  ← 没有缺少依赖的 skills
```

**TypeScript 对齐验证**:
```typescript
// openclaw/src/commands/onboard-skills.ts
const installable = missing.filter(
  (skill) => skill.install.length > 0 && skill.missing.bins.length > 0
);
if (installable.length > 0) {  // ✅ 只有当有可安装的依赖时才显示
  const toInstall = await prompter.multiselect(...);
}
```

**结论**: Python 版本已经**完全对齐** TypeScript 版本。当所有 skills 都已经 eligible 时，不应该显示安装界面。这是正确的！

---

## 问题 2: Moonshot API Key 错误 ✅ 已修复

### 症状
```
ERROR | No API key found for moonshot
RuntimeError: No API key found for moonshot
```

### 根本原因

#### 原因 1: 配置文件使用错误的模型
```json
// ~/.openclaw/openclaw.json (修复前)
{
  "agents": {
    "defaults": {
      "model": "moonshot/kimi-k2.5"  // ❌ 这是标准 Moonshot API
    }
  }
}
```

您应该使用 **Kimi Coding API**，不是标准 Moonshot API！

#### 原因 2: Auth profile provider 名称错误
```json
// ~/.openclaw/agents/main/agent/auth-profiles.json (修复前)
{
  "profiles": {
    "kimi-code:default": {  // ❌ 错误: "kimi-code"
      "provider": "kimi-code",
      "key": "sk-kimi-..."
    }
  }
}
```

正确的 provider 名称应该是 `"kimi-coding"`，不是 `"kimi-code"`！

### 修复操作

#### 修复 1: 更新模型配置
```bash
# 已执行
# 备份: ~/.openclaw/openclaw.json.before_fix
```

修复后:
```json
{
  "agents": {
    "defaults": {
      "model": "kimi-coding/k2p5"  // ✅ Kimi Coding API
    }
  }
}
```

#### 修复 2: 更新 auth profile
```bash
# 已执行
# 备份: ~/.openclaw/agents/main/agent/auth-profiles.json.before_fix
```

修复后:
```json
{
  "profiles": {
    "kimi-coding:default": {  // ✅ 正确: "kimi-coding"
      "provider": "kimi-coding",
      "key": "sk-kimi-EeDcQZ4AQhZInffbP9WSNXYBhPzCxo0rA7t0P6nNgThnbokEnxvzFqkZuFoHH9sD"
    }
  }
}
```

---

## 验证修复

### 步骤 1: 检查配置
```bash
# 检查模型配置
grep -A 3 '"model"' ~/.openclaw/openclaw.json
# 应该输出: "model": "kimi-coding/k2p5"

# 检查 auth profile
cat ~/.openclaw/agents/main/agent/auth-profiles.json | python3 -m json.tool
# 应该看到 "kimi-coding:default" 和 provider: "kimi-coding"
```

### 步骤 2: 重启 Gateway
```bash
# 停止当前 gateway (Ctrl+C)
# 然后重启
cd /Users/long/Desktop/XJarvis/openclaw-python
uv run openclaw start
```

### 步骤 3: 验证启动日志
预期看到:
```
✅ 不应出现 "No API key found for moonshot" 错误
✅ 应该显示 "Using provider: kimi-coding"
✅ 应该显示 "Using model: k2p5"
```

### 步骤 4: 测试对话
浏览器访问 http://localhost:3000，发送消息测试。

---

## 为什么之前的 onboarding 没有正确配置？

### 可能的原因

1. **Provider 名称混淆**
   - Onboarding 时可能输入了 `kimi-code` 或其他变体
   - 应该输入: `kimi-coding`

2. **模型名称错误**
   - 选择了 `kimi-k2.5` (这是 Moonshot API 的模型)
   - 应该选择: `k2p5` (Kimi Coding API 的模型)

### 正确的 Onboarding 流程

如果需要重新 onboarding:
```bash
# 清理配置
rm -rf ~/.openclaw/agents/main
rm ~/.openclaw/openclaw.json

# 重新 onboarding
cd /Users/long/Desktop/XJarvis/openclaw-python
uv run openclaw onboard

# 关键配置:
# Provider: 输入 "kimi-coding" (不是 kimi-code!)
# Model: 输入 "k2p5" (不是 kimi-k2.5!)
# API Key: 输入您的 Kimi Coding API key
```

---

## 对齐状态总结

### ✅ 已完全对齐

| 功能 | Python | TypeScript | 状态 |
|-----|--------|-----------|------|
| Kimi Coding API 支持 | AnthropicProvider | anthropic-messages | ✅ |
| Provider Base URL | `https://api.kimi.com/coding/` | `https://api.kimi.com/coding/` | ✅ |
| Skills 配置流程 | 当 `installable.length > 0` 时显示 | 当 `installable.length > 0` 时显示 | ✅ |
| QuickStart/Advanced | 相同的 skills 流程 | 相同的 skills 流程 | ✅ |

### ✅ 配置已修复

| 配置项 | 修复前 | 修复后 | 状态 |
|-------|--------|--------|------|
| 模型 | `moonshot/kimi-k2.5` | `kimi-coding/k2p5` | ✅ |
| Auth Provider | `kimi-code` | `kimi-coding` | ✅ |
| API Key | 已存在但 provider 不匹配 | 已匹配正确 provider | ✅ |

---

## 备份文件位置

如果需要回滚:
```bash
# 配置文件备份
~/.openclaw/openclaw.json.before_fix
~/.openclaw/openclaw.json.bak

# Auth profile 备份
~/.openclaw/agents/main/agent/auth-profiles.json.before_fix
```

---

## 现在可以测试了！

```bash
# 重启 gateway
cd /Users/long/Desktop/XJarvis/openclaw-python
uv run openclaw start

# 浏览器访问
open http://localhost:3000

# 发送测试消息
"你好，测试 Kimi Coding API"
```

预期结果:
- ✅ 正常响应
- ✅ 使用 Kimi Coding k2p5 模型
- ✅ 不出现 API key 错误
