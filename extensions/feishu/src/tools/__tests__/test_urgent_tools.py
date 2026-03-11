"""Tests for urgent_tools.

Mirrors: clawdbot-feishu/src/__tests__/urgent-tools.test.ts
"""
import asyncio
import pytest
from unittest.mock import MagicMock

from src.tools.urgent_tools.register import run_feishu_urgent, register_urgent_tools


def _success_resp(data=None):
    resp = MagicMock()
    resp.success.return_value = True
    resp.data = data or MagicMock()
    resp.data.invalid_user_id_list = []
    return resp


def _error_resp(code=99999, msg="err"):
    resp = MagicMock()
    resp.success.return_value = False
    resp.code = code
    resp.msg = msg
    return resp


class TestFeishuUrgent:
    def test_sends_app_buzz(self):
        client = MagicMock()
        client.im.v1.message.urgent_app.return_value = _success_resp()

        async def run():
            return await run_feishu_urgent(
                {"message_id": "om_123", "user_ids": ["ou_abc"], "urgent_type": "app"},
                client,
            )

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result["details"]["ok"] is True
        assert result["details"]["urgent_type"] == "app"
        client.im.v1.message.urgent_app.assert_called_once()

    def test_sends_sms_buzz(self):
        client = MagicMock()
        client.im.v1.message.urgent_sms.return_value = _success_resp()

        async def run():
            return await run_feishu_urgent(
                {"message_id": "om_123", "user_ids": ["ou_abc"], "urgent_type": "sms"},
                client,
            )

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result["details"]["ok"] is True
        client.im.v1.message.urgent_sms.assert_called_once()

    def test_requires_message_id(self):
        client = MagicMock()

        async def run():
            return await run_feishu_urgent({"user_ids": ["ou_abc"]}, client)

        result = asyncio.get_event_loop().run_until_complete(run())
        assert "error" in result["details"]

    def test_requires_user_ids(self):
        client = MagicMock()

        async def run():
            return await run_feishu_urgent({"message_id": "om_123", "user_ids": []}, client)

        result = asyncio.get_event_loop().run_until_complete(run())
        assert "error" in result["details"]

    def test_invalid_urgent_type(self):
        client = MagicMock()

        async def run():
            return await run_feishu_urgent(
                {"message_id": "om_123", "user_ids": ["ou_abc"], "urgent_type": "fax"},
                client,
            )

        result = asyncio.get_event_loop().run_until_complete(run())
        assert "error" in result["details"]

    def test_quota_exceeded_returns_friendly_error(self):
        client = MagicMock()
        client.im.v1.message.urgent_app.return_value = _error_resp(230024, "quota exceeded")

        async def run():
            return await run_feishu_urgent(
                {"message_id": "om_123", "user_ids": ["ou_abc"], "urgent_type": "app"},
                client,
            )

        result = asyncio.get_event_loop().run_until_complete(run())
        assert "error" in result["details"]
        assert "quota" in result["details"]["error"].lower()

    def test_includes_invalid_user_list(self):
        client = MagicMock()
        resp_data = MagicMock()
        resp_data.invalid_user_id_list = ["ou_invalid"]
        resp = MagicMock()
        resp.success.return_value = True
        resp.data = resp_data
        client.im.v1.message.urgent_app.return_value = resp

        async def run():
            return await run_feishu_urgent(
                {"message_id": "om_123", "user_ids": ["ou_valid", "ou_invalid"], "urgent_type": "app"},
                client,
            )

        result = asyncio.get_event_loop().run_until_complete(run())
        assert "ou_invalid" in result["details"]["invalid_user_list"]

    def test_registration(self):
        registered = {}
        api = MagicMock()
        api.register_tool = lambda name, description, schema, handler: registered.update({name: handler})
        register_urgent_tools(api)
        assert "feishu_urgent" in registered
