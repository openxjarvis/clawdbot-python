# Kimi Coding 修复验证和测试指南

## 修复完成 ✅

### 核心变更总结

#### 1. **Kimi Coding API 支持** (runtime.py)
```python
# ✅ 修复前: 使用 OpenAIProvider (错误)
if provider_name in ("kimi-coding", "kimi"):
    return OpenAIProvider(...)  # ❌

# ✅ 修复后: 使用 AnthropicProvider (正确)
if provider_name in ("kimi-coding", "kimi"):
    kwargs["base_url"] = "https://api.kimi.com/coding/"  # ✅ 尾部斜杠
    return AnthropicProvider(provider_name_override="kimi-coding", **kwargs)  # ✅
```

#### 2. **Provider Base URLs 对齐** (pi_stream.py)
```python
# ✅ 与 TypeScript 完全对齐
PROVIDER_BASE_URLS = {
    "moonshot": "https://api.moonshot.ai/v1",       # ✅ 国际版 (默认)
    "kimi-coding": "https://api.kimi.com/coding/",  # ✅ Anthropic API
    "kimi": "https://api.kimi.com/coding/",         # ✅ Anthropic API
    # ... 所有其他 providers
}
```

#### 3. **QuickStart Skills 对齐** (onboard_skills.py)
```python
# ✅ 所有模式 (QuickStart/Advanced) 都使用相同流程
should_configure = prompter.confirm("Configure skills now? (recommended)", default=True)
if should_configure:
    selected = prompter.checkbox("Install missing skill dependencies", choices=choices)
    # ... 安装选中的 skills
```

#### 4. **环境变量加载** (infra/dotenv.py + cli/main.py)
```python
# ✅ 统一在 CLI 入口加载，优先级: System > CWD > Global > Config
@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context):
    load_dot_env(quiet=True)  # ✅ 所有命令统一加载
```

---

## 完整测试流程

### 前提条件
```bash
# 确保环境
cd /Users/long/Desktop/XJarvis/openclaw-python

# 检查 uv 环境
uv --version

# 确认有 Kimi API key
echo $KIMI_API_KEY  # 或准备好 API key
```

---

## 测试 A: Kimi Coding API 完整流程

### 步骤 1: 清理旧配置
```bash
# 备份当前配置（可选）
[ -d ~/.openclaw/agents/main ] && cp -r ~/.openclaw/agents/main ~/.openclaw/agents/main.backup.$(date +%Y%m%d_%H%M%S)

# 清理旧配置
rm -rf ~/.openclaw/agents/main/agent/openclaw.json
rm -rf ~/.openclaw/agents/main/agent/auth-profiles.json

# 或完全清理
# rm -rf ~/.openclaw/agents/main
```

### 步骤 2: 设置 API Key
```bash
# 方法 A: 环境变量（推荐用于测试）
export KIMI_API_KEY="your-kimi-coding-api-key"

# 方法 B: 全局 .env 文件
mkdir -p ~/.openclaw
cat > ~/.openclaw/.env << 'EOF'
KIMI_API_KEY=your-kimi-coding-api-key
EOF

# 方法 C: 项目 .env 文件
cat > /Users/long/Desktop/XJarvis/openclaw-python/.env << 'EOF'
KIMI_API_KEY=your-kimi-coding-api-key
EOF
```

### 步骤 3: 运行 Onboarding
```bash
cd /Users/long/Desktop/XJarvis/openclaw-python

# QuickStart 流程
uv run openclaw onboard --flow quickstart --accept-risk

# 操作步骤:
# 1. 选择 provider: 输入 "kimi-coding" 或 "12" (如果在列表中)
# 2. 选择模型: 输入 "k2p5" (Kimi Coding 默认模型)
# 3. ✅ 验证: 应该看到 "Configure skills now? (recommended)" 提示
# 4. ✅ 验证: 选择 Yes 后，应该看到多选 skills 安装界面
# 5. 选择需要的 skills (可以都不选，直接回车)
# 6. 完成 onboarding
```

### 步骤 4: 验证配置
```bash
# 检查生成的配置文件
cat ~/.openclaw/agents/main/agent/openclaw.json

# 预期输出应包含:
# {
#   "models": {
#     "default": "kimi-coding/k2p5"
#   },
#   "agentId": "main",
#   ...
# }

# 检查 auth profiles
cat ~/.openclaw/agents/main/agent/auth-profiles.json | jq '.profiles."kimi-coding:default"'

# 预期输出:
# {
#   "type": "api_key",
#   "provider": "kimi-coding",
#   "key": "your-kimi-api-key..."
# }
```

### 步骤 5: 启动测试
```bash
# 启动 Gateway
uv run openclaw start

# 预期输出:
# ✅ 不应出现 "No API key found for moonshot" 错误
# ✅ 不应出现 "OpenAIProvider" 相关错误
# ✅ 应该显示正确的 Kimi Coding 配置

# 浏览器访问 http://localhost:3000
# 测试对话:
# - 输入: "你好，测试 Kimi Coding API"
# - ✅ 预期: 正常响应，使用 Kimi Coding k2p5 模型
```

### 步骤 6: 检查日志
```bash
# 查看 gateway 日志
tail -f ~/.openclaw/agents/main/agent/gateway.log

# ✅ 应该看到:
# - "Using provider: kimi-coding"
# - "Using model: k2p5"
# - 不应出现 "Falling back to..." 消息
# - 不应出现 "User location is not supported" 错误
```

---

## 测试 B: QuickStart Skills 对齐验证

### 步骤 1: QuickStart 模式
```bash
cd /Users/long/Desktop/XJarvis/openclaw-python

# 清理配置
rm -rf ~/.openclaw/agents/main

# 运行 QuickStart
uv run openclaw onboard --flow quickstart --accept-risk

# ✅ 验证检查点:
# 1. [ ] 看到 "Configure skills now? (recommended)" 提示
# 2. [ ] 选择 Yes 后，看到 "Install missing skill dependencies" 多选界面
# 3. [ ] 可以选择 brew, npm, uv, go 等依赖
# 4. [ ] 可以选择跳过（选择 "Skip (continue without installing)"）
```

### 步骤 2: Advanced 模式对比
```bash
# 清理配置
rm -rf ~/.openclaw/agents/main

# 运行 Advanced
uv run openclaw onboard --flow advanced

# ✅ 验证检查点:
# 1. [ ] 看到 "Configure skills now? (recommended)" 提示（与 QuickStart 相同）
# 2. [ ] 选择 Yes 后，看到相同的多选安装界面（与 QuickStart 相同）
# 3. [ ] Skills 配置流程完全一致
```

---

## 测试 C: 环境变量加载优先级

### 测试脚本
```bash
cd /Users/long/Desktop/XJarvis/openclaw-python

# 创建测试环境变量
export TEST_SYSTEM_VAR="from-system"

# 创建 CWD .env
cat > .env << 'EOF'
TEST_CWD_VAR=from-cwd
TEST_SYSTEM_VAR=from-cwd-override
EOF

# 创建 Global .env
mkdir -p ~/.openclaw
cat > ~/.openclaw/.env << 'EOF'
TEST_GLOBAL_VAR=from-global
TEST_CWD_VAR=from-global-override
EOF

# 运行测试
uv run python << 'EOF'
import os
from openclaw.infra.dotenv import load_dot_env

# 清理环境
for k in list(os.environ.keys()):
    if k.startswith('TEST_'):
        del os.environ[k]

# 设置 system 变量
os.environ['TEST_SYSTEM_VAR'] = 'from-system'

# 加载 dotenv
load_dot_env(quiet=False)

# 验证优先级
print("\n=== 环境变量优先级测试 ===")
print(f"TEST_SYSTEM_VAR: {os.getenv('TEST_SYSTEM_VAR')}")   # ✅ 应该是 'from-system'
print(f"TEST_CWD_VAR: {os.getenv('TEST_CWD_VAR')}")         # ✅ 应该是 'from-cwd'
print(f"TEST_GLOBAL_VAR: {os.getenv('TEST_GLOBAL_VAR')}")   # ✅ 应该是 'from-global'

# 预期结果:
# TEST_SYSTEM_VAR: from-system       (System env 优先级最高，不被覆盖)
# TEST_CWD_VAR: from-cwd              (CWD .env 优先于 Global .env)
# TEST_GLOBAL_VAR: from-global        (Global .env 正常加载)
EOF

# 清理测试文件
rm .env
rm ~/.openclaw/.env
unset TEST_SYSTEM_VAR
```

---

## 测试 D: Provider Routing 验证

### 测试脚本
```bash
cd /Users/long/Desktop/XJarvis/openclaw-python

# 创建 provider routing 测试
cat > test_providers.py << 'EOF'
import os
os.environ['KIMI_API_KEY'] = 'test-key'
os.environ['MOONSHOT_API_KEY'] = 'test-key'

from openclaw.agents.runtime import MultiProviderRuntime

runtime = MultiProviderRuntime()

providers_to_test = [
    ("moonshot", "OpenAIProvider", "https://api.moonshot.ai/v1"),
    ("kimi-coding", "AnthropicProvider", "https://api.kimi.com/coding/"),
    ("kimi", "AnthropicProvider", "https://api.kimi.com/coding/"),
]

print("\n=== Provider Routing 测试 ===\n")
for provider_name, expected_class, expected_url in providers_to_test:
    provider = runtime._create_provider(provider_name)
    actual_class = type(provider).__name__
    actual_url = getattr(provider, '_base_url', 'N/A')
    
    status = "✅" if (actual_class == expected_class and actual_url == expected_url) else "❌"
    print(f"{status} {provider_name:15} -> {actual_class:25} base_url={actual_url}")
    
    if actual_class != expected_class:
        print(f"   ❌ Expected class: {expected_class}")
    if actual_url != expected_url:
        print(f"   ❌ Expected URL: {expected_url}")

print("\n预期所有测试通过 (✅)")
EOF

# 运行测试
uv run python test_providers.py

# 清理
rm test_providers.py
```

---

## 测试 E: 与 TypeScript 对齐验证

### 对比 Checklist

```bash
# Python 配置
cat ~/.openclaw/agents/main/agent/openclaw.json

# TypeScript 配置（如果有）
cat ~/.openclaw/agents/main/agent/openclaw.json  # 应该是相同的格式
```

#### 配置格式对齐验证
- [ ] `models.default` 格式: `"provider/model-id"` ✅
- [ ] `models.providers.kimi-coding.baseUrl` 可选覆盖 ✅
- [ ] `agentId` 字段存在 ✅
- [ ] `gateway` 配置格式一致 ✅

#### API 行为对齐验证
- [ ] Kimi Coding 使用 Anthropic Messages API ✅
- [ ] Moonshot 使用 OpenAI Completions API ✅
- [ ] Base URLs 完全一致 ✅
- [ ] API Key 查找顺序一致 ✅

#### Onboarding 流程对齐验证
- [ ] QuickStart/Advanced 都有 skills 配置步骤 ✅
- [ ] Skills 多选界面一致 ✅
- [ ] 提示语言一致 ✅

---

## 故障排查

### 问题 1: "No API key found for moonshot"
**原因**: 配置中使用了 `moonshot/kimi-k2.5` 但没有设置 `MOONSHOT_API_KEY`

**解决方案**:
```bash
# 选项 A: 改用 Kimi Coding
uv run openclaw onboard
# 选择 provider: kimi-coding
# 模型: k2p5

# 选项 B: 设置 Moonshot API key
export MOONSHOT_API_KEY="your-moonshot-key"
```

### 问题 2: "User location is not supported"
**原因**: 使用了 Google Gemini API 而不是 Kimi/Moonshot

**解决方案**:
```bash
# 检查配置
cat ~/.openclaw/agents/main/agent/openclaw.json

# 确保 models.default 是:
# "kimi-coding/k2p5" 或 "moonshot/moonshot-v1-8k"

# 不应该是:
# "google/gemini-2.0-flash" ❌
```

### 问题 3: QuickStart 没有 skills 配置步骤
**原因**: 使用了旧版本代码

**解决方案**:
```bash
# 确认已应用最新修复
cd /Users/long/Desktop/XJarvis/openclaw-python
git log --oneline -1
# 应该看到 "修复 Kimi Coding API 支持..." 提交

# 重新运行
uv run openclaw onboard --flow quickstart --accept-risk
```

### 问题 4: AnthropicProvider 错误
**原因**: Kimi Coding 特有的 Anthropic API 格式问题

**解决方案**:
```bash
# 检查 base_url 是否有尾部斜杠
grep -r "kimi.com/coding" openclaw/agents/

# 应该输出:
# openclaw/agents/runtime.py:    kwargs["base_url"] = ... "https://api.kimi.com/coding/"  # ✅
```

---

## 成功验证标志

### ✅ 修复成功的标志

1. **Onboarding 成功**
   - QuickStart 和 Advanced 都有 "Configure skills now?" 提示
   - 可以看到 skills 多选安装界面
   - 配置文件正确生成在 `~/.openclaw/agents/main/agent/`

2. **启动成功**
   - `uv run openclaw start` 无错误
   - 日志显示正确的 provider 和 model
   - 浏览器可以访问 http://localhost:3000

3. **对话成功**
   - 发送消息后正常响应
   - 不出现 API 错误
   - Response 来自配置的模型（Kimi Coding k2p5）

4. **Provider Routing 正确**
   - `kimi-coding` -> `AnthropicProvider`
   - `moonshot` -> `OpenAIProvider`
   - Base URLs 与 TypeScript 一致

---

## 回归测试（可选）

### 其他 Providers 验证
```bash
# 测试 Anthropic
export ANTHROPIC_API_KEY="your-key"
uv run openclaw onboard
# 选择: anthropic/claude-3-5-sonnet-20241022

# 测试 OpenAI
export OPENAI_API_KEY="your-key"
uv run openclaw onboard
# 选择: openai/gpt-4o

# 测试 Google
export GOOGLE_API_KEY="your-key"
uv run openclaw onboard
# 选择: google/gemini-2.0-flash

# 每个都应该正常工作 ✅
```

---

## 文档参考

### 修复详情
- `docs/development/KIMI_CODING_FIX.md` - Kimi Coding 修复说明
- `docs/development/ALIGNMENT_STATUS.md` - 完整对齐状态
- `docs/development/CHANGELOG_ALIGNMENT.md` - 变更日志

### TypeScript 参考
- `openclaw/src/agents/models-config.providers.ts` - Provider 配置
- `openclaw/src/wizard/onboarding.ts` - Onboarding 流程
- `openclaw/src/commands/onboard-skills.ts` - Skills 配置

---

## 下一步

完成测试后:
1. ✅ 确认所有测试通过
2. 📝 记录任何问题或边缘情况
3. 🚀 可以正常使用 Kimi Coding API
4. 📊 考虑添加自动化测试覆盖这些场景
