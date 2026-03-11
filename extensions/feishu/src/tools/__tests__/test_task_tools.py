"""Tests for task_tools.

Mirrors: clawdbot-feishu/src/__tests__/task-tools.test.ts
"""
import asyncio
import pytest
from unittest.mock import MagicMock


def _success_resp(data=None):
    resp = MagicMock()
    resp.success.return_value = True
    resp.data = data or MagicMock()
    return resp


def _error_resp(code=99999, msg="err"):
    resp = MagicMock()
    resp.success.return_value = False
    resp.code = code
    resp.msg = msg
    return resp


def _mock_task(guid="task-123"):
    t = MagicMock()
    t.guid = guid
    t.task_id = guid
    t.summary = "Test Task"
    t.description = ""
    t.completed_at = ""
    t.due = None
    t.start = None
    t.is_milestone = False
    t.url = ""
    t.created_at = "1700000000000"
    t.updated_at = "1700000000000"
    return t


class TestTaskCreate:
    def test_creates_task(self):
        from src.tools.task_tools.register import _dispatch
        client = MagicMock()
        task_data = MagicMock()
        task_data.task = _mock_task("task-abc")
        client.task.v2.task.create.return_value = _success_resp(task_data)

        async def run():
            return await _dispatch("feishu_task_create", {"summary": "Hello Task"}, client)

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result["details"]["task"]["guid"] == "task-abc"
        assert result["details"]["task"]["summary"] == "Test Task"


class TestTaskGet:
    def test_gets_task(self):
        from src.tools.task_tools.register import _dispatch
        client = MagicMock()
        task_data = MagicMock()
        task_data.task = _mock_task("task-xyz")
        client.task.v2.task.get.return_value = _success_resp(task_data)

        async def run():
            return await _dispatch("feishu_task_get", {"task_guid": "task-xyz"}, client)

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result["details"]["task"]["guid"] == "task-xyz"


class TestTaskDelete:
    def test_deletes_task(self):
        from src.tools.task_tools.register import _dispatch
        client = MagicMock()
        client.task.v2.task.delete.return_value = _success_resp()

        async def run():
            return await _dispatch("feishu_task_delete", {"task_guid": "task-del"}, client)

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result["details"]["success"] is True
        assert result["details"]["task_guid"] == "task-del"


class TestTasklistCreate:
    def test_creates_tasklist(self):
        from src.tools.task_tools.register import _dispatch
        client = MagicMock()
        tl_data = MagicMock()
        tl = MagicMock()
        tl.guid = "tl-123"
        tl.name = "My List"
        tl.url = ""
        tl.created_at = "1700000000000"
        tl.updated_at = "1700000000000"
        tl_data.tasklist = tl
        client.task.v2.tasklist.create.return_value = _success_resp(tl_data)

        async def run():
            return await _dispatch("feishu_tasklist_create", {"name": "My List"}, client)

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result["details"]["tasklist"]["guid"] == "tl-123"


class TestTaskCommentCreate:
    def test_creates_comment(self):
        from src.tools.task_tools.register import _dispatch
        client = MagicMock()
        c_data = MagicMock()
        c = MagicMock()
        c.id = "cmt-1"
        c.content = "Great job!"
        c.created_at = "1700000000000"
        c.updated_at = "1700000000000"
        c_data.comment = c
        client.task.v2.comment.create.return_value = _success_resp(c_data)

        async def run():
            return await _dispatch(
                "feishu_task_comment_create",
                {"task_guid": "task-1", "content": "Great job!"},
                client,
            )

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result["details"]["comment"]["id"] == "cmt-1"


class TestTaskToolRegistration:
    def test_registers_all_23_tools(self):
        from src.tools.task_tools.register import register_task_tools

        registered = []
        api = MagicMock()
        api.register_tool = lambda name, **kwargs: registered.append(name)
        register_task_tools(api)
        assert len(registered) == 23
        # Check key tool names
        assert "feishu_task_create" in registered
        assert "feishu_tasklist_create" in registered
        assert "feishu_task_comment_create" in registered
        assert "feishu_task_attachment_upload" in registered
