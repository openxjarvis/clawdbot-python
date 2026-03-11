"""Tests for tools_common/api.py and tools_common/context.py.

Mirrors: clawdbot-feishu/src/__tests__/tools-common.test.ts
"""
import asyncio
import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.tools.tools_common.api import (
    json_result,
    error_result,
    feishu_ok,
    run_feishu_api_call,
)
from src.tools.tools_common.context import (
    run_with_feishu_tool_context,
    get_current_feishu_account_id,
)


class TestJsonResult:
    def test_returns_content_and_details(self):
        data = {"foo": "bar", "n": 42}
        result = json_result(data)
        assert result["details"] == data
        assert result["content"][0]["type"] == "text"
        parsed = json.loads(result["content"][0]["text"])
        assert parsed == data

    def test_ensures_ascii_false(self):
        data = {"msg": "你好"}
        result = json_result(data)
        assert "你好" in result["content"][0]["text"]

    def test_error_result_wraps_exception(self):
        result = error_result(ValueError("something went wrong"))
        assert result["details"]["error"] == "something went wrong"

    def test_error_result_wraps_string(self):
        result = error_result("oops")
        assert result["details"]["error"] == "oops"


class TestFeishuOk:
    def test_success_true(self):
        mock = MagicMock()
        mock.success.return_value = True
        assert feishu_ok(mock) is True

    def test_success_false(self):
        mock = MagicMock()
        mock.success.return_value = False
        assert feishu_ok(mock) is False

    def test_no_success_method(self):
        assert feishu_ok(object()) is False


class TestRunFeishuApiCall:
    def test_success_on_first_attempt(self):
        mock_resp = MagicMock()
        mock_resp.success.return_value = True

        async def run():
            return await run_feishu_api_call("test.op", lambda: mock_resp)

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result is mock_resp

    def test_raises_on_api_error_code(self):
        mock_resp = MagicMock()
        mock_resp.success.return_value = False
        mock_resp.code = 99999
        mock_resp.msg = "some error"
        mock_resp.request_id = None
        mock_resp.x_tt_logid = None

        async def run():
            return await run_feishu_api_call("test.op", lambda: mock_resp, backoff_ms=[])

        with pytest.raises(RuntimeError, match="test.op failed"):
            asyncio.get_event_loop().run_until_complete(run())

    def test_retries_on_retryable_code(self):
        call_count = 0

        def mock_fn():
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            if call_count < 3:
                resp.success.return_value = False
                resp.code = 1254290
                resp.msg = "transient"
                resp.request_id = None
                resp.x_tt_logid = None
            else:
                resp.success.return_value = True
            return resp

        async def run():
            return await run_feishu_api_call(
                "test.retry", mock_fn,
                retryable_codes=[1254290],
                backoff_ms=[1, 1],  # small delays for test speed
            )

        result = asyncio.get_event_loop().run_until_complete(run())
        assert call_count == 3
        assert feishu_ok(result)

    def test_raises_after_all_retries_exhausted(self):
        def mock_fn():
            resp = MagicMock()
            resp.success.return_value = False
            resp.code = 1254290
            resp.msg = "always fail"
            resp.request_id = None
            resp.x_tt_logid = None
            return resp

        async def run():
            return await run_feishu_api_call(
                "test.exhaust", mock_fn,
                retryable_codes=[1254290],
                backoff_ms=[1, 1],
            )

        with pytest.raises(RuntimeError):
            asyncio.get_event_loop().run_until_complete(run())


class TestToolContext:
    def test_default_is_none(self):
        assert get_current_feishu_account_id() is None

    def test_sets_account_id_in_context(self):
        async def run():
            assert get_current_feishu_account_id() is None
            async with run_with_feishu_tool_context("acc-123"):
                assert get_current_feishu_account_id() == "acc-123"
            assert get_current_feishu_account_id() is None

        asyncio.get_event_loop().run_until_complete(run())

    def test_nested_contexts(self):
        async def run():
            async with run_with_feishu_tool_context("outer"):
                assert get_current_feishu_account_id() == "outer"
                async with run_with_feishu_tool_context("inner"):
                    assert get_current_feishu_account_id() == "inner"
                assert get_current_feishu_account_id() == "outer"

        asyncio.get_event_loop().run_until_complete(run())
