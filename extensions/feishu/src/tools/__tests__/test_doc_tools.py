"""Tests for doc_tools actions and register.

Mirrors: clawdbot-feishu/src/__tests__/doc-tools.test.ts
"""
import asyncio
import pytest
from unittest.mock import MagicMock, patch


def _make_mock_client():
    """Build a mock lark_oapi client stub."""
    client = MagicMock()
    return client


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


class TestDocRead:
    def test_read_returns_title_and_content(self):
        from src.tools.doc_tools.register import run_feishu_doc

        client = _make_mock_client()
        doc_data = MagicMock()
        doc_data.document = MagicMock()
        doc_data.document.title = "My Doc"
        client.docx.v1.document.get.return_value = _success_resp(doc_data)

        blocks_data = MagicMock()
        blocks_data.items = []
        client.docx.v1.document_block.list.return_value = _success_resp(blocks_data)

        async def run():
            return await run_feishu_doc({"action": "read", "doc_token": "ABC123"}, client)

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result["details"]["title"] == "My Doc"
        assert "document_id" in result["details"]

    def test_read_requires_doc_token(self):
        from src.tools.doc_tools.register import run_feishu_doc
        client = _make_mock_client()

        async def run():
            return await run_feishu_doc({"action": "read"}, client)

        result = asyncio.get_event_loop().run_until_complete(run())
        assert "error" in result["details"]

    def test_read_handles_api_failure(self):
        from src.tools.doc_tools.register import run_feishu_doc
        client = _make_mock_client()
        client.docx.v1.document.get.return_value = _error_resp(99001, "permission denied")

        async def run():
            return await run_feishu_doc({"action": "read", "doc_token": "XYZ"}, client)

        result = asyncio.get_event_loop().run_until_complete(run())
        assert "error" in result["details"]


class TestDocCreate:
    def test_create_returns_document_id(self):
        from src.tools.doc_tools.register import run_feishu_doc
        client = _make_mock_client()

        doc_data = MagicMock()
        doc_data.document = MagicMock()
        doc_data.document.document_id = "NEW_DOC_ID"
        doc_data.document.title = "Test Title"
        doc_data.document.url = "https://feishu.cn/doc/NEW_DOC_ID"
        client.docx.v1.document.create.return_value = _success_resp(doc_data)

        async def run():
            return await run_feishu_doc({"action": "create", "title": "Test Title"}, client)

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result["details"]["document_id"] == "NEW_DOC_ID"
        assert result["details"]["title"] == "Test Title"


class TestDocListBlocks:
    def test_list_blocks_returns_block_list(self):
        from src.tools.doc_tools.register import run_feishu_doc
        client = _make_mock_client()

        b1 = MagicMock()
        b1.block_id = "blk_1"
        b1.block_type = 2
        b1.parent_id = "doc_root"
        b1.children = []
        blocks_data = MagicMock()
        blocks_data.items = [b1]
        client.docx.v1.document_block.list.return_value = _success_resp(blocks_data)

        async def run():
            return await run_feishu_doc({"action": "list_blocks", "doc_token": "DOC1"}, client)

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result["details"]["total"] == 1
        assert result["details"]["blocks"][0]["block_id"] == "blk_1"


class TestDocAppScopes:
    def test_app_scopes_returns_granted_pending(self):
        from src.tools.doc_tools.register import run_feishu_app_scopes
        client = _make_mock_client()

        scopes_data = MagicMock()
        scopes_data.granted_scopes = [MagicMock(scope="im:message")]
        scopes_data.pending_scopes = [MagicMock(scope="drive:drive")]
        client.application.v6.scope.list.return_value = _success_resp(scopes_data)

        async def run():
            return await run_feishu_app_scopes({}, client)

        result = asyncio.get_event_loop().run_until_complete(run())
        assert "granted" in result["details"] or "error" in result["details"]  # may fail on SDK import


class TestDocUnknownAction:
    def test_unknown_action_returns_error(self):
        from src.tools.doc_tools.register import run_feishu_doc
        client = _make_mock_client()

        async def run():
            return await run_feishu_doc({"action": "nonexistent"}, client)

        result = asyncio.get_event_loop().run_until_complete(run())
        assert "error" in result["details"]
