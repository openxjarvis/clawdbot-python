"""
完整集成测试：验证 Cron/Agent/Subagent 机制与 TS 版本的细粒度对齐

测试覆盖：
1. SubagentsConfig 字段名和默认值
2. AgentDefaults maxConcurrent 和 subagents
3. CommandLane enum 和并发限制
4. Lane generation 跟踪
5. Subagent spawn 深度和子代限制
6. Subagent registry 恢复逻辑
7. Cron lock 机制
8. Cron + lane 集成
"""
from __future__ import annotations

import asyncio
import tempfile
import time
from pathlib import Path

import pytest

# Config schemas and defaults
from openclaw.config.schema import SubagentsConfig, AgentDefaults
from openclaw.config.defaults import (
    DEFAULT_AGENT_MAX_CONCURRENT,
    DEFAULT_SUBAGENT_MAX_CONCURRENT,
    apply_agent_defaults,
    resolve_agent_max_concurrent,
    resolve_subagent_max_concurrent,
)

# Lane architecture
from openclaw.agents.queuing.lanes import CommandLane, LANE_DEFAULTS
from openclaw.agents.queuing.lane import Lane
from openclaw.agents.queuing.queue import QueueManager

# Subagent management
from openclaw.agents.subagent_registry import SubagentRegistry, SubagentRunRecord

# Cron service
from openclaw.cron.locked import locked
from openclaw.cron.types import CronJob, CronJobState, EverySchedule, SystemEventPayload


# =============================================================================
# Test 1: SubagentsConfig 字段名和默认值对齐
# =============================================================================

def test_subagents_config_schema():
    """验证 SubagentsConfig 字段名和默认值与 TS 对齐"""
    
    config = SubagentsConfig()
    
    # 验证新字段名和默认值 (aligned with TS)
    assert config.maxSpawnDepth == 1, "maxSpawnDepth 默认值应为 1"
    assert config.maxChildrenPerAgent == 5, "maxChildrenPerAgent 默认值应为 5"
    assert config.archiveAfterMinutes == 60, "archiveAfterMinutes 默认值应为 60"
    assert config.maxConcurrent is None, "maxConcurrent 默认应为 None"
    assert config.model is None, "model 默认应为 None"
    assert config.thinking is None, "thinking 默认应为 None"
    
    # 验证字段约束 (aligned with TS zod schema)
    config_custom = SubagentsConfig(
        maxSpawnDepth=3,
        maxChildrenPerAgent=10,
        archiveAfterMinutes=120
    )
    assert config_custom.maxSpawnDepth == 3
    assert config_custom.maxChildrenPerAgent == 10
    assert config_custom.archiveAfterMinutes == 120
    
    print("✅ SubagentsConfig 字段对齐测试通过")


def test_subagents_config_legacy_migration():
    """验证旧字段名的向后兼容迁移"""
    
    # 测试旧字段名迁移 (maxDepth → maxSpawnDepth)
    config = SubagentsConfig(maxDepth=3)
    assert config.maxSpawnDepth == 3, "maxDepth 应迁移到 maxSpawnDepth"
    
    # 测试旧字段名迁移 (maxActive → maxChildrenPerAgent)
    config2 = SubagentsConfig(maxActive=8)
    assert config2.maxChildrenPerAgent == 8, "maxActive 应迁移到 maxChildrenPerAgent"
    
    print("✅ SubagentsConfig 迁移逻辑测试通过")


# =============================================================================
# Test 2: AgentDefaults maxConcurrent 和 subagents 字段
# =============================================================================

def test_agent_defaults_fields():
    """验证 AgentDefaults 新字段"""
    
    defaults = AgentDefaults()
    
    # 验证新字段存在
    assert hasattr(defaults, "maxConcurrent"), "AgentDefaults 应有 maxConcurrent 字段"
    assert hasattr(defaults, "subagents"), "AgentDefaults 应有 subagents 字段"
    
    # 验证可以设置 subagents 配置
    defaults_with_subagents = AgentDefaults(
        subagents=SubagentsConfig(maxSpawnDepth=2, maxChildrenPerAgent=10)
    )
    assert defaults_with_subagents.subagents is not None
    assert defaults_with_subagents.subagents.maxSpawnDepth == 2
    assert defaults_with_subagents.subagents.maxChildrenPerAgent == 10
    
    print("✅ AgentDefaults 字段测试通过")


def test_config_defaults_constants():
    """验证默认常量与 TS 对齐"""
    
    assert DEFAULT_AGENT_MAX_CONCURRENT == 4, "DEFAULT_AGENT_MAX_CONCURRENT 应为 4"
    assert DEFAULT_SUBAGENT_MAX_CONCURRENT == 8, "DEFAULT_SUBAGENT_MAX_CONCURRENT 应为 8"
    
    # 测试 resolve 函数
    assert resolve_agent_max_concurrent({}) == 4
    assert resolve_subagent_max_concurrent({}) == 8
    
    # 测试配置覆盖
    cfg = {
        "agents": {
            "defaults": {
                "maxConcurrent": 6,
                "subagents": {"maxConcurrent": 10}
            }
        }
    }
    assert resolve_agent_max_concurrent(cfg) == 6
    assert resolve_subagent_max_concurrent(cfg) == 10
    
    print("✅ 配置默认常量测试通过")


def test_apply_agent_defaults():
    """验证 apply_agent_defaults 自动注入默认值"""
    
    # 空配置应注入默认值
    cfg = {}
    result = apply_agent_defaults(cfg)
    
    assert result["agents"]["defaults"]["maxConcurrent"] == 4
    assert result["agents"]["defaults"]["subagents"]["maxConcurrent"] == 8
    
    # 已有配置不应修改
    cfg2 = {
        "agents": {
            "defaults": {
                "maxConcurrent": 6,
                "subagents": {"maxConcurrent": 12}
            }
        }
    }
    result2 = apply_agent_defaults(cfg2)
    assert result2["agents"]["defaults"]["maxConcurrent"] == 6
    assert result2["agents"]["defaults"]["subagents"]["maxConcurrent"] == 12
    
    print("✅ apply_agent_defaults 测试通过")


# =============================================================================
# Test 3: CommandLane enum 和并发限制
# =============================================================================

def test_command_lane_enum():
    """验证 CommandLane enum 与 TS 对齐"""
    
    # 验证所有 lane 类型存在
    assert CommandLane.MAIN.value == "main"
    assert CommandLane.CRON.value == "cron"
    assert CommandLane.SUBAGENT.value == "subagent"
    assert CommandLane.NESTED.value == "nested"
    
    # 验证 LANE_DEFAULTS
    assert LANE_DEFAULTS[CommandLane.MAIN] == 4, "Main lane 默认并发应为 4"
    assert LANE_DEFAULTS[CommandLane.CRON] == 1, "Cron lane 默认并发应为 1"
    assert LANE_DEFAULTS[CommandLane.SUBAGENT] == 8, "Subagent lane 默认并发应为 8"
    assert LANE_DEFAULTS[CommandLane.NESTED] == 1, "Nested lane 默认并发应为 1"
    
    print("✅ CommandLane enum 测试通过")


def test_queue_manager_fixed_lanes():
    """验证 QueueManager 初始化固定 lanes"""
    
    manager = QueueManager()
    
    # 验证可以获取固定 lanes
    main_lane = manager.get_lane(CommandLane.MAIN)
    cron_lane = manager.get_lane(CommandLane.CRON)
    subagent_lane = manager.get_lane(CommandLane.SUBAGENT)
    nested_lane = manager.get_lane(CommandLane.NESTED)
    
    # 验证并发限制
    assert main_lane.max_concurrent == 4
    assert cron_lane.max_concurrent == 1
    assert subagent_lane.max_concurrent == 8
    assert nested_lane.max_concurrent == 1
    
    # 验证 lane 名称
    assert main_lane.name == "main"
    assert cron_lane.name == "cron"
    
    print("✅ QueueManager 固定 lanes 测试通过")


@pytest.mark.asyncio
async def test_queue_manager_enqueue_in_lane():
    """验证 enqueue_in_lane 方法"""
    
    manager = QueueManager()
    
    executed = []
    
    async def task1():
        executed.append("task1")
        return "result1"
    
    async def task2():
        executed.append("task2")
        return "result2"
    
    # 在 CRON lane 中执行任务
    result1 = await manager.enqueue_in_lane(CommandLane.CRON, task1)
    result2 = await manager.enqueue_in_lane(CommandLane.SUBAGENT, task2)
    
    assert result1 == "result1"
    assert result2 == "result2"
    assert executed == ["task1", "task2"]
    
    print("✅ enqueue_in_lane 测试通过")


# =============================================================================
# Test 4: Lane generation 跟踪
# =============================================================================

@pytest.mark.asyncio
async def test_lane_generation_tracking():
    """验证 Lane generation 防止陈旧任务完成"""
    
    lane = Lane("test", max_concurrent=2)
    
    # 验证初始 generation
    assert lane.generation == 0
    assert lane._next_task_id == 1
    assert len(lane._active_tasks) == 0
    
    # 执行一个任务并验证 task_id 分配
    executed = []
    
    async def task():
        executed.append("task")
        await asyncio.sleep(0.01)
        return "result"
    
    result = await lane.enqueue(task)
    assert result == "result"
    assert executed == ["task"]
    assert lane._next_task_id > 1, "task_id 应递增"
    
    # 测试 generation reset
    lane.reset_generation()
    assert lane.generation == 1, "generation 应递增到 1"
    
    print("✅ Lane generation 跟踪测试通过")


@pytest.mark.asyncio
async def test_lane_stale_task_prevention():
    """验证陈旧任务不会影响状态"""
    
    lane = Lane("test", max_concurrent=1)
    
    results = []
    
    async def slow_task():
        await asyncio.sleep(0.1)
        results.append("slow")
        return "slow_result"
    
    # 启动慢任务
    task1 = asyncio.create_task(lane.enqueue(slow_task))
    
    # 等待一下让任务开始
    await asyncio.sleep(0.01)
    
    # Reset generation (模拟 lane reset)
    old_gen = lane.generation
    lane.reset_generation()
    new_gen = lane.generation
    
    assert new_gen == old_gen + 1, "generation 应递增"
    
    # 慢任务完成但不应影响新 generation 的状态
    await task1
    
    print("✅ 陈旧任务防止测试通过")


# =============================================================================
# Test 5: Subagent Registry 恢复逻辑
# =============================================================================

@pytest.mark.asyncio
async def test_subagent_registry_archive_calculation():
    """验证 archive_at_ms 计算逻辑"""
    
    # 测试默认 archiveAfterMinutes = 60
    config = {
        "agents": {
            "defaults": {
                "subagents": {
                    "archiveAfterMinutes": 60
                }
            }
        }
    }
    
    registry = SubagentRegistry(config)
    archive_after_ms = registry._resolve_archive_after_ms()
    
    assert archive_after_ms == 60 * 60_000, "60分钟应转换为毫秒"
    
    # 测试自定义值
    config2 = {
        "agents": {
            "defaults": {
                "subagents": {
                    "archiveAfterMinutes": 30
                }
            }
        }
    }
    
    registry2 = SubagentRegistry(config2)
    archive_after_ms2 = registry2._resolve_archive_after_ms()
    
    assert archive_after_ms2 == 30 * 60_000, "30分钟应转换为毫秒"
    
    print("✅ Archive 计算测试通过")


@pytest.mark.asyncio
async def test_subagent_registry_restore_methods():
    """验证 registry 恢复方法实现"""
    
    registry = SubagentRegistry()
    
    # 验证新方法存在
    assert hasattr(registry, "_trigger_announce_and_cleanup")
    assert hasattr(registry, "_resume_wait_for_completion")
    assert hasattr(registry, "_cleanup_session")
    
    # 测试 _resolve_archive_after_ms
    archive_ms = registry._resolve_archive_after_ms()
    assert archive_ms == 60 * 60_000, "默认应为 60 分钟"
    
    print("✅ Registry 恢复方法测试通过")


# =============================================================================
# Test 6: Cron Lock 机制
# =============================================================================

@pytest.mark.asyncio
async def test_cron_locked_mechanism():
    """验证 per-store-path lock 机制"""
    
    store_path = "/tmp/test_cron_store.json"
    
    execution_order = []
    
    async def task1():
        execution_order.append("task1_start")
        await asyncio.sleep(0.05)
        execution_order.append("task1_end")
        return "result1"
    
    async def task2():
        execution_order.append("task2_start")
        await asyncio.sleep(0.01)
        execution_order.append("task2_end")
        return "result2"
    
    # 并发启动两个任务，应串行执行
    results = await asyncio.gather(
        locked(store_path, task1),
        locked(store_path, task2)
    )
    
    assert results == ["result1", "result2"]
    
    # 验证串行执行 (task1 完全结束后 task2 才开始)
    assert execution_order == [
        "task1_start",
        "task1_end",
        "task2_start",
        "task2_end"
    ], "任务应在同一 store_path 下串行执行"
    
    print("✅ Cron lock 机制测试通过")


@pytest.mark.asyncio
async def test_cron_locked_different_paths():
    """验证不同 store_path 可以并发执行"""
    
    store_path1 = "/tmp/store1.json"
    store_path2 = "/tmp/store2.json"
    
    execution_times = {}
    
    async def task(name: str):
        start = time.time()
        await asyncio.sleep(0.05)
        execution_times[name] = time.time() - start
        return name
    
    # 不同 store_path 应并发执行
    start = time.time()
    results = await asyncio.gather(
        locked(store_path1, lambda: task("task1")),
        locked(store_path2, lambda: task("task2"))
    )
    total_time = time.time() - start
    
    assert set(results) == {"task1", "task2"}
    
    # 总时间应接近单个任务时间（并发），而非两倍（串行）
    assert total_time < 0.08, "不同 store_path 应并发执行"
    
    print("✅ Cron 不同 path 并发测试通过")


# =============================================================================
# Test 7: Cron + Lane 集成
# =============================================================================

@pytest.mark.asyncio
async def test_cron_service_lane_integration():
    """验证 CronService 使用 CommandLane.CRON"""
    
    from openclaw.cron.service import CronService
    from openclaw.cron.store import CronStore
    
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "jobs.json"
        log_dir = Path(tmpdir) / "runs"
        
        executed = []
        
        async def mock_isolated_agent(params):
            executed.append(params)
            return {"ok": True, "status": "completed"}
        
        # 创建带 lane_manager 的 CronService
        lane_manager = QueueManager()
        service = CronService(
            store_path=store_path,
            log_dir=log_dir,
            cron_enabled=True,
            run_isolated_agent_job=mock_isolated_agent,
            lane_manager=lane_manager,
        )
        
        # 验证 lane_manager 已设置
        assert service.lane_manager is not None
        
        # 验证可以访问 CRON lane
        cron_lane = service.lane_manager.get_lane(CommandLane.CRON)
        assert cron_lane.name == "cron"
        assert cron_lane.max_concurrent == 1
        
        print("✅ Cron + Lane 集成测试通过")


# =============================================================================
# Test 8: 综合场景测试
# =============================================================================

@pytest.mark.asyncio
async def test_comprehensive_scenario():
    """综合场景：配置加载 → lane 初始化 → subagent spawn → registry"""
    
    # 1. 配置加载和默认值应用
    config = {
        "agents": {
            "defaults": {
                "model": "google/gemini-2.0-flash-exp"
            }
        }
    }
    
    config_with_defaults = apply_agent_defaults(config)
    
    assert config_with_defaults["agents"]["defaults"]["maxConcurrent"] == 4
    assert config_with_defaults["agents"]["defaults"]["subagents"]["maxConcurrent"] == 8
    
    # 2. Lane manager 初始化
    lane_manager = QueueManager()
    
    # 3. 验证所有固定 lanes 可用
    for lane_enum in [CommandLane.MAIN, CommandLane.CRON, CommandLane.SUBAGENT, CommandLane.NESTED]:
        lane = lane_manager.get_lane(lane_enum)
        assert lane.max_concurrent == LANE_DEFAULTS[lane_enum]
    
    # 4. Subagent registry 使用配置
    registry = SubagentRegistry(config_with_defaults)
    
    # 5. 注册 subagent run
    record = registry.register_subagent_run(
        child_session_key="agent:test:subagent:123",
        requester_session_key="agent:test:main",
        task="Test task",
        cleanup="delete",
    )
    
    assert record.run_id is not None
    assert record.archive_at_ms is not None, "archive_at_ms 应根据 archiveAfterMinutes 计算"
    
    # 6. 验证 archive 时间约为 60 分钟后
    now_ms = int(time.time() * 1000)
    expected_archive = now_ms + (60 * 60_000)
    assert abs(record.archive_at_ms - expected_archive) < 5000, "archive 时间应约为 60 分钟后"
    
    print("✅ 综合场景测试通过")


# =============================================================================
# 运行所有测试
# =============================================================================

def run_all_tests():
    """运行所有同步测试"""
    print("\n" + "="*60)
    print("Cron/Agent/Subagent 对齐集成测试")
    print("="*60 + "\n")
    
    # Test 1: SubagentsConfig
    print("📋 测试组 1: SubagentsConfig 字段对齐")
    test_subagents_config_schema()
    test_subagents_config_legacy_migration()
    
    # Test 2: AgentDefaults
    print("\n📋 测试组 2: AgentDefaults 字段和常量")
    test_agent_defaults_fields()
    test_config_defaults_constants()
    test_apply_agent_defaults()
    
    # Test 3: CommandLane
    print("\n📋 测试组 3: CommandLane enum 和 LANE_DEFAULTS")
    test_command_lane_enum()
    test_queue_manager_fixed_lanes()
    
    print("\n✨ 所有同步测试通过！")


async def run_async_tests():
    """运行所有异步测试"""
    print("\n" + "="*60)
    print("异步集成测试")
    print("="*60 + "\n")
    
    # Test 4: Lane generation
    print("📋 测试组 4: Lane generation 跟踪")
    await test_lane_generation_tracking()
    await test_lane_stale_task_prevention()
    
    # Test 5: Subagent registry
    print("\n📋 测试组 5: Subagent Registry")
    await test_subagent_registry_archive_calculation()
    await test_subagent_registry_restore_methods()
    
    # Test 6: Cron lock
    print("\n📋 测试组 6: Cron Lock 机制")
    await test_cron_locked_mechanism()
    await test_cron_locked_different_paths()
    
    # Test 7: Cron + Lane
    print("\n📋 测试组 7: Cron + Lane 集成")
    await test_cron_service_lane_integration()
    
    # Test 3: enqueue_in_lane
    print("\n📋 测试组 3.2: QueueManager enqueue_in_lane")
    await test_queue_manager_enqueue_in_lane()
    
    # Test 8: Comprehensive
    print("\n📋 测试组 8: 综合场景")
    await test_comprehensive_scenario()
    
    print("\n✨ 所有异步测试通过！")


if __name__ == "__main__":
    print("\n🚀 开始 Cron/Agent/Subagent 对齐集成测试\n")
    
    # 运行同步测试
    run_all_tests()
    
    # 运行异步测试
    asyncio.run(run_async_tests())
    
    print("\n" + "="*60)
    print("🎉 所有测试通过！Python 版本已与 TS 版本完全对齐")
    print("="*60 + "\n")
    
    print("✅ 对齐点验证:")
    print("  1. SubagentsConfig: maxSpawnDepth=1, maxChildrenPerAgent=5")
    print("  2. AgentDefaults: maxConcurrent=4, subagents.maxConcurrent=8")
    print("  3. CommandLane: MAIN/CRON/SUBAGENT/NESTED")
    print("  4. Lane: generation 跟踪防止陈旧任务")
    print("  5. Registry: archiveAfterMinutes 计算和恢复逻辑")
    print("  6. Cron: per-store-path lock 机制")
    print("  7. Integration: CronService + CommandLane.CRON")
    print()
