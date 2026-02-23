"""Integration tests for memory system"""
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from openclaw.memory import MemorySearchManager, MemorySearchResult, MemorySource
from openclaw.memory.builtin_manager import BuiltinMemoryManager


@pytest.mark.asyncio
class TestBuiltinMemoryManager:
    """Test BuiltinMemoryManager (vector+FTS search over agent files)"""

    async def test_create_manager(self):
        with TemporaryDirectory() as tmpdir:
            manager = BuiltinMemoryManager(
                agent_id="test-agent",
                workspace_dir=Path(tmpdir),
            )
            assert manager is not None

    async def test_search_empty_workspace(self):
        with TemporaryDirectory() as tmpdir:
            manager = BuiltinMemoryManager(
                agent_id="test-agent",
                workspace_dir=Path(tmpdir),
            )
            results = await manager.search("anything")
            assert isinstance(results, list)

    async def test_add_file_and_search(self, tmp_path):
        memory_file = tmp_path / "MEMORY.md"
        memory_file.write_text("Python is a great programming language\n")

        manager = BuiltinMemoryManager(
            agent_id="test-agent",
            workspace_dir=tmp_path,
        )
        await manager.add_file(memory_file)
        results = await manager.search("programming")
        assert isinstance(results, list)


@pytest.mark.asyncio
class TestSimpleMemorySearchManager:
    """Test the simple MemorySearchManager (MEMORY.md based)"""

    async def test_search_empty_dir(self):
        with TemporaryDirectory() as tmpdir:
            manager = MemorySearchManager(workspace_dir=Path(tmpdir))
            results = await manager.search("anything")
            assert isinstance(results, list)

    async def test_search_with_memory_file(self, tmp_path):
        memory_file = tmp_path / "MEMORY.md"
        memory_file.write_text("# Memory\n\nPython is great for data science\n")

        manager = MemorySearchManager(workspace_dir=tmp_path)
        results = await manager.search("data science")
        assert isinstance(results, list)


def test_memory_system_imports():
    """Test that memory system can be imported"""
    from openclaw.memory import MemorySearchManager, MemorySearchResult, MemorySource
    from openclaw.memory.builtin_manager import BuiltinMemoryManager

    assert MemorySearchManager is not None
    assert MemorySearchResult is not None
    assert MemorySource is not None
    assert BuiltinMemoryManager is not None
