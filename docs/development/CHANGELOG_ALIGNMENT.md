# OpenClaw Python Alignment Update Log

## 2026-03-10 - QuickStart Skills 安装对齐（修正版）

### 问题描述

Python 版本的 openclaw 在 QuickStart 模式下完全跳过了 skills 安装流程，只提供 API Key 配置。

### TypeScript 实际行为确认

经过仔细检查 TypeScript 源码（`src/commands/onboard-skills.ts`），发现：
- ✅ TypeScript 的 `setupSkills()` **不区分 QuickStart/Advanced 模式**
- ✅ **总是会询问用户** "Configure skills now? (recommended)"
- ✅ 询问之后提供相同的多选安装界面
- ✅ 没有针对 QuickStart 的特殊处理

### 修复内容

**修改文件**: `openclaw/wizard/onboard_skills.py`

**主要变更**:

1. **移除 QuickStart 特殊逻辑**:
   - 删除了 QuickStart 模式下的提前返回
   - 删除了只配置 API Key 的简化流程

2. **统一询问逻辑**:
   ```python
   # 所有模式都询问用户（与 TypeScript 一致）
   should_configure = prompter.confirm(
       "Configure skills now? (recommended)",
       default=True,
   )
   ```

3. **统一安装流程**:
   - QuickStart 和 Advanced 模式使用完全相同的代码路径
   - 相同的多选界面
   - 相同的安装逻辑
   - 相同的 API Key 配置流程

### 对比

**之前的错误理解**:
- ❌ 认为 QuickStart 应该跳过询问直接显示列表
- ❌ 为 QuickStart 添加了特殊处理

**实际 TypeScript 行为**:
- ✅ QuickStart 和 Advanced 在 skills 配置上**完全一样**
- ✅ 都会询问 "Configure skills now?"
- ✅ 都使用相同的多选和安装流程

**修正后的 Python 行为**:
- ✅ 现在与 TypeScript 100% 一致
- ✅ 没有针对模式的特殊处理
- ✅ 代码更简洁、更易维护

### 关键发现

TypeScript 的 QuickStart 模式的"快速"体现在：
1. ❌ **不是**跳过 skills 配置询问
2. ✅ 而是在 **gateway 配置、channel 配置等其他环节**采用默认值
3. ✅ Skills 配置环节与 Advanced 模式**完全相同**

### 影响范围

- ✅ 100% 与 TypeScript 行为对齐
- ✅ 用户在 QuickStart 和 Advanced 模式下都能配置 skills
- ✅ 代码更简洁（移除了不必要的特殊处理）
- ✅ 向后兼容（两种模式行为统一）

### 测试建议

```bash
# QuickStart 模式测试
uv run openclaw onboard --flow quickstart --accept-risk

# 预期行为：
# 1. 显示 skills 状态摘要
# 2. 询问 "Configure skills now? (recommended)"
# 3. 如果选择 Yes，显示多选列表
# 4. 安装选中的 skills

# Advanced 模式测试
uv run openclaw onboard --flow advanced --accept-risk

# 预期行为：与 QuickStart 在 skills 配置环节**完全相同**
```

### 代码统计

- 文件修改: 1 个
- 行数变化: +14 -42 (删除了冗余的 QuickStart 特殊处理)
- 功能对齐: 100%

### 相关文档

- 对齐状态报告: `docs/development/ALIGNMENT_STATUS.md`（需要更新）
- 原始计划: `.cursor/plans/openclaw_python_alignment_check_06e8cb1c.plan.md`

---

## 之前的更新

### 2026-03-10 - 环境变量加载对齐

**修改文件**:
- `openclaw/cli/main.py` - 添加统一的 dotenv 加载
- `openclaw/cli/gateway_cmd.py` - 删除重复加载
- `.env.example` - 添加加载优先级说明

**结果**: 100% 与 TypeScript 版本对齐

**详情**: 见之前的更新日志

---

**维护**: OpenClaw Team  
**最后更新**: 2026-03-10

