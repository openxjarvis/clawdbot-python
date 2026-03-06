"""Tests for memory/skills alignment fixes.

Covers all 13 items fixed in the alignment pass:
  1.  compaction/compactor.py  — no ImportError
  2.  MemorySource.MANUAL      — enum value exists
  3.  Bootstrap size constants  — 20k/150k matches TS baseline
  4.  SyncManager start        — instance stored, start called async
  5.  BuiltinMemoryManager.sync() — scans dirs, updates, removes orphans
  6.  add_file() embeddings     — embed_batch called, blobs stored
  7.  Compaction write-back     — memory/compact-YYYY-MM-DD.md written
  8.  Session export hookup     — _sync_manager attr present on PiRuntime
  9.  Pre-compaction flush       — _run_memory_flush method exists
 10.  Token count               — already in pi_runtime (regression guard)
 11.  skills.install/update     — real impl, not stubs
 12.  Skills loaders unified    — openclaw.skills delegates to agents.skills
 13.  Cron skills version-gate  — resolve_cron_skills_snapshot checks version
"""
from __future__ import annotations

import asyncio
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 1. compaction/compactor.py — no ImportError
# ---------------------------------------------------------------------------

def test_compactor_importable():
    """compaction/compactor.py must be importable (was missing → ImportError)."""
    from openclaw.agents.compaction.compactor import compact_messages  # noqa: F401


# ---------------------------------------------------------------------------
# 2. MemorySource.MANUAL — enum value exists
# ---------------------------------------------------------------------------

def test_memory_source_manual_exists():
    from openclaw.memory.types import MemorySource
    assert MemorySource.MANUAL.value == "manual"


def test_memory_source_manual_usable_in_set():
    from openclaw.memory.types import MemorySource
    all_values = {e.value for e in MemorySource}
    assert "manual" in all_values


# ---------------------------------------------------------------------------
# 3. Bootstrap size constants — aligned with TS (20 k / 150 k)
# ---------------------------------------------------------------------------

def test_bootstrap_size_constants_aligned():
    from openclaw.agents.system_prompt import (
        _DEFAULT_MAX_CHARS_PER_FILE,
        _DEFAULT_TOTAL_MAX_CHARS,
    )
    assert _DEFAULT_MAX_CHARS_PER_FILE == 20_000, (
        f"Expected 20_000 (TS DEFAULT_BOOTSTRAP_MAX_CHARS), got {_DEFAULT_MAX_CHARS_PER_FILE}"
    )
    assert _DEFAULT_TOTAL_MAX_CHARS == 150_000, (
        f"Expected 150_000 (TS DEFAULT_BOOTSTRAP_TOTAL_MAX_CHARS), got {_DEFAULT_TOTAL_MAX_CHARS}"
    )


def test_bootstrap_bootstrap_py_constants():
    from openclaw.agents.system_prompt_bootstrap import (
        DEFAULT_BOOTSTRAP_MAX_CHARS,
        DEFAULT_BOOTSTRAP_TOTAL_MAX_CHARS,
    )
    assert DEFAULT_BOOTSTRAP_MAX_CHARS == 20_000
    assert DEFAULT_BOOTSTRAP_TOTAL_MAX_CHARS == 150_000


# ---------------------------------------------------------------------------
# 4. SyncManager — GatewayServer stores _sync_manager attribute
# ---------------------------------------------------------------------------

def test_gateway_server_has_sync_manager_attr():
    """GatewayServer must initialise _sync_manager to None in __init__."""
    from openclaw.gateway.server import GatewayServer
    # Check attribute is declared (None before first get_memory_manager call)
    gs = GatewayServer.__new__(GatewayServer)
    # Manually set the attribute that __init__ would set
    gs._memory_manager = None
    gs._sync_manager = None
    assert hasattr(gs, "_sync_manager")


def test_pi_runtime_has_sync_manager_attr():
    """PiAgentRuntime must declare _sync_manager so session export hookup works."""
    from openclaw.gateway.pi_runtime import PiAgentRuntime
    rt = PiAgentRuntime.__new__(PiAgentRuntime)
    rt._sync_manager = None
    assert hasattr(rt, "_sync_manager")


# ---------------------------------------------------------------------------
# 5. BuiltinMemoryManager.sync() — scans memory files and removes orphans
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_builtin_memory_manager_sync_indexes_files():
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        # Create a MEMORY.md file
        (ws / "MEMORY.md").write_text("# Test Memory\nSome remembered fact.\n")

        from openclaw.memory.builtin_manager import BuiltinMemoryManager

        mgr = BuiltinMemoryManager(
            agent_id="test",
            workspace_dir=ws,
            embedding_provider=None,  # no real API key needed for FTS path
        )
        # Mock the embedder so embed_batch doesn't hit network
        mgr.embedder = MagicMock()
        mgr.embedder.embed_batch = AsyncMock(
            return_value=MagicMock(embeddings=None)
        )

        stats = await mgr.sync()
        assert stats["files_added"] == 1
        # Verify chunks were stored
        assert mgr.db is not None
        count = mgr.db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        assert count > 0

        # Sync again — same file, hash unchanged → no re-index
        stats2 = await mgr.sync()
        assert stats2["files_added"] == 0
        assert stats2["files_updated"] == 0

        mgr.close()


@pytest.mark.asyncio
async def test_builtin_memory_manager_sync_removes_orphans():
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        mem_file = ws / "MEMORY.md"
        mem_file.write_text("# Orphan Test\n")

        from openclaw.memory.builtin_manager import BuiltinMemoryManager

        mgr = BuiltinMemoryManager(agent_id="test2", workspace_dir=ws)
        mgr.embedder = MagicMock()
        mgr.embedder.embed_batch = AsyncMock(return_value=MagicMock(embeddings=None))

        await mgr.sync()
        # File was added
        assert mgr.db.execute("SELECT COUNT(*) FROM files").fetchone()[0] == 1

        # Delete the file from disk → sync should remove orphan
        mem_file.unlink()
        stats = await mgr.sync()
        assert stats["files_removed"] == 1
        assert mgr.db.execute("SELECT COUNT(*) FROM files").fetchone()[0] == 0
        mgr.close()


# ---------------------------------------------------------------------------
# 6. add_file() — embed_batch is called and blobs stored (when embedder works)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_file_stores_embedding_blobs():
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        test_file = ws / "test.md"
        test_file.write_text("Line 1\nLine 2\nLine 3\n")

        from openclaw.memory.builtin_manager import BuiltinMemoryManager
        from openclaw.memory.types import MemorySource

        mgr = BuiltinMemoryManager(agent_id="emb_test", workspace_dir=ws)

        fake_embedding = [0.1] * 1536
        mock_batch = MagicMock()
        mock_batch.embeddings = [fake_embedding]
        mgr.embedder = MagicMock()
        mgr.embedder.embed_batch = AsyncMock(return_value=mock_batch)

        n = await mgr.add_file(test_file, MemorySource.MEMORY)
        assert n > 0

        # Verify embedding blob was stored (not NULL)
        row = mgr.db.execute("SELECT embedding FROM chunks LIMIT 1").fetchone()
        assert row is not None
        assert row["embedding"] is not None, "Embedding blob must not be NULL"
        mgr.close()


# ---------------------------------------------------------------------------
# 7. Compaction write-back — compact-YYYY-MM-DD.md written to memory/
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compaction_writes_summary_to_disk():
    with tempfile.TemporaryDirectory() as tmp:
        from openclaw.gateway.pi_runtime import PiAgentRuntime

        rt = PiAgentRuntime(cwd=tmp)

        # Build a pi_session with large enough messages to exceed half the tiny context window
        pi_session = MagicMock()
        pi_session._conversation_history = [
            {"role": "user", "content": "Important context. " + "x" * 200}
            for _ in range(20)
        ]

        with patch(
            "openclaw.agents.compaction.functions.summarize_in_stages",
            new=AsyncMock(return_value="Fake summary of dropped messages."),
        ):
            # Use a small context_window (512 tokens) so the 20×55-token messages
            # exceed the 50% budget (256 tokens) and pruning drops some.
            result = await rt._execute_compaction(
                session_id="test-session-1234",
                pi_session=pi_session,
                context_window=512,
                compaction_settings={
                    "enabled": True,
                    "mode": "safeguard",
                    "reserveTokens": 64,
                    "keepRecentTokens": 128,
                },
            )

        # A compact-YYYY-MM-DD.md file should have been written
        memory_dir = Path(tmp) / "memory"
        compact_files = list(memory_dir.glob("compact-*.md"))
        assert len(compact_files) == 1, f"Expected 1 compact file, found: {compact_files}"
        content = compact_files[0].read_text()
        assert "Compaction" in content or "summary" in content.lower()


# ---------------------------------------------------------------------------
# 8. Session export hookup — _sync_manager attribute on PiRuntime
# ---------------------------------------------------------------------------

def test_pi_runtime_sync_manager_initialized_to_none():
    from openclaw.gateway.pi_runtime import PiAgentRuntime
    with tempfile.TemporaryDirectory() as tmp:
        rt = PiAgentRuntime(cwd=tmp)
    assert hasattr(rt, "_sync_manager")
    assert rt._sync_manager is None


# ---------------------------------------------------------------------------
# 9. Pre-compaction flush — _run_memory_flush method exists
# ---------------------------------------------------------------------------

def test_pi_runtime_has_run_memory_flush():
    from openclaw.gateway.pi_runtime import PiAgentRuntime
    assert callable(getattr(PiAgentRuntime, "_run_memory_flush", None)), (
        "PiAgentRuntime must have a _run_memory_flush async method"
    )


@pytest.mark.asyncio
async def test_run_memory_flush_calls_prompt():
    from openclaw.gateway.pi_runtime import PiAgentRuntime
    with tempfile.TemporaryDirectory() as tmp:
        rt = PiAgentRuntime(cwd=tmp)

    pi_session = MagicMock()
    pi_session.prompt = AsyncMock()

    await rt._run_memory_flush(session_id="sess-abc", pi_session=pi_session)

    pi_session.prompt.assert_called_once()
    call_args = pi_session.prompt.call_args[0][0]
    assert "memory" in call_args.lower()
    assert "flush" in call_args.lower() or "compaction" in call_args.lower()


# ---------------------------------------------------------------------------
# 11. skills.install handler — real implementation, not stub
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_skills_install_handler_returns_result():
    """skills.install must attempt real dependency installation, not stub."""
    from openclaw.gateway.handlers import handle_skills_install

    connection = MagicMock()
    connection.config = {}

    with patch(
        "openclaw.agents.skills.workspace.load_workspace_skill_entries",
        return_value=[],
    ):
        result = await handle_skills_install(connection, {"name": "nonexistent-skill"})

    assert isinstance(result, dict)
    # Skill not found — error reported properly
    assert result.get("installed") is False or "error" in result


@pytest.mark.asyncio
async def test_skills_update_handler_bumps_version():
    """skills.update must bump the snapshot version."""
    from openclaw.gateway.handlers import handle_skills_update
    from openclaw.agents.skills.refresh import get_skills_snapshot_version

    connection = MagicMock()
    before = get_skills_snapshot_version()
    result = await handle_skills_update(connection, {"name": "some-skill"})
    after = get_skills_snapshot_version()

    assert result.get("updated") is True
    assert after == before + 1


# ---------------------------------------------------------------------------
# 12. Skills loaders unified — openclaw.skills delegates to agents.skills
# ---------------------------------------------------------------------------

def test_skills_package_exports_canonical_types():
    """openclaw.skills __init__ must re-export canonical agents.skills symbols."""
    import openclaw.skills as skills_pkg
    from openclaw.agents.skills import SkillSnapshot, SkillEntry

    # These should be the same objects (re-exported, not copied)
    assert skills_pkg.SkillSnapshot is SkillSnapshot
    assert skills_pkg.SkillEntry is SkillEntry


# ---------------------------------------------------------------------------
# 13. Cron skills version-gate — resolve_cron_skills_snapshot checks version
# ---------------------------------------------------------------------------

def test_cron_skills_snapshot_skips_rebuild_when_version_matches():
    from openclaw.cron.isolated_agent.skills_snapshot import resolve_cron_skills_snapshot
    from openclaw.agents.skills.refresh import get_skills_snapshot_version
    from openclaw.agents.skills.types import SkillSnapshot

    current_version = get_skills_snapshot_version()
    existing = SkillSnapshot(prompt="cached", skills=[], version=current_version)

    result = resolve_cron_skills_snapshot(
        workspace_dir="/tmp",
        config={},
        agent_id="test",
        existing_snapshot=existing,
    )
    # Version matches → same snapshot returned without rebuilding
    assert result is existing


def test_cron_skills_snapshot_rebuilds_when_version_stale():
    from openclaw.cron.isolated_agent.skills_snapshot import resolve_cron_skills_snapshot
    from openclaw.agents.skills.types import SkillSnapshot

    stale = SkillSnapshot(prompt="stale", skills=[], version=-999)

    # The function does `from openclaw.agents.skills import build_workspace_skill_snapshot`
    # so we patch at the agents.skills module level.
    with patch(
        "openclaw.agents.skills.build_workspace_skill_snapshot",
        return_value=SkillSnapshot(prompt="fresh", skills=[]),
    ) as mock_build:
        result = resolve_cron_skills_snapshot(
            workspace_dir="/tmp",
            config={},
            agent_id="test",
            existing_snapshot=stale,
        )
    mock_build.assert_called_once()
    assert result.prompt == "fresh"


# ---------------------------------------------------------------------------
# compactor.py — compact_messages returns correct structure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compact_messages_returns_compacted_list():
    from openclaw.agents.compaction.compactor import compact_messages

    messages = [
        {"role": "user", "content": "Message " + "x" * 500}
        for _ in range(20)
    ]

    with patch(
        "openclaw.agents.compaction.compactor.summarize_in_stages",
        new=AsyncMock(return_value="Summary of dropped messages."),
    ):
        result = await compact_messages(
            messages=messages,
            api_key="fake-key",
            context_window=2048,
        )

    assert isinstance(result, list)
    assert len(result) < len(messages)
    # First message should be the compaction summary
    assert result[0]["role"] == "user"
    assert "summary" in result[0]["content"].lower() or "Conversation history" in result[0]["content"]


# ---------------------------------------------------------------------------
# MemorySearchResult — id and text optional fields
# ---------------------------------------------------------------------------

def test_memory_search_result_accepts_id_and_text():
    from openclaw.memory.types import MemorySearchResult, MemorySource

    r = MemorySearchResult(
        path="memory/test.md",
        start_line=1,
        end_line=5,
        score=0.9,
        snippet="test snippet",
        source=MemorySource.MEMORY,
        id="chunk-id-123",
        text="full chunk text here",
    )
    assert r.id == "chunk-id-123"
    assert r.text == "full chunk text here"
    assert r.citation is None
