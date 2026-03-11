"""Tests for bitable_tools.

Mirrors: clawdbot-feishu/src/__tests__/bitable-tools.test.ts
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


class TestBitableGetMeta:
    def test_parses_base_url(self):
        from src.tools.bitable_tools.register import _dispatch
        client = MagicMock()

        tables_data = MagicMock()
        t1 = MagicMock()
        t1.table_id = "tbl_xxx"
        t1.name = "Sheet1"
        t1.revision = 1
        tables_data.items = [t1]
        client.bitable.v1.app_table.list.return_value = _success_resp(tables_data)

        async def run():
            return await _dispatch(
                "feishu_bitable_get_meta",
                {"url": "https://feishu.cn/base/ABC123?table=tbl_xxx"},
                client,
            )

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result["details"]["app_token"] == "ABC123"
        assert len(result["details"]["tables"]) == 1

    def test_requires_url(self):
        from src.tools.bitable_tools.register import _dispatch
        client = MagicMock()

        async def run():
            return await _dispatch("feishu_bitable_get_meta", {}, client)

        result = asyncio.get_event_loop().run_until_complete(run())
        assert "error" in result["details"]


class TestBitableListFields:
    def test_returns_fields_with_type_names(self):
        from src.tools.bitable_tools.register import _dispatch
        client = MagicMock()

        fields_data = MagicMock()
        f1 = MagicMock()
        f1.field_id = "fld_1"
        f1.field_name = "Name"
        f1.type = 1
        f1.is_primary = True
        f1.description = None
        fields_data.items = [f1]
        client.bitable.v1.app_table_field.list.return_value = _success_resp(fields_data)

        async def run():
            return await _dispatch(
                "feishu_bitable_list_fields",
                {"app_token": "APP1", "table_id": "TBL1"},
                client,
            )

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result["details"]["total"] == 1
        assert result["details"]["fields"][0]["type_name"] == "Text"


class TestBitableListRecords:
    def test_returns_paginated_records(self):
        from src.tools.bitable_tools.register import _dispatch
        client = MagicMock()

        records_data = MagicMock()
        r1 = MagicMock()
        r1.record_id = "rec_1"
        r1.fields = {"Name": "Alice"}
        records_data.items = [r1]
        records_data.has_more = False
        records_data.page_token = ""
        records_data.total = 1
        client.bitable.v1.app_table_record.list.return_value = _success_resp(records_data)

        async def run():
            return await _dispatch(
                "feishu_bitable_list_records",
                {"app_token": "APP1", "table_id": "TBL1", "page_size": 10},
                client,
            )

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result["details"]["records"][0]["record_id"] == "rec_1"
        assert result["details"]["records"][0]["fields"]["Name"] == "Alice"


class TestBitableCreateRecord:
    def test_creates_record_returns_id(self):
        from src.tools.bitable_tools.register import _dispatch
        client = MagicMock()

        record_data = MagicMock()
        new_rec = MagicMock()
        new_rec.record_id = "rec_new"
        new_rec.fields = {"Name": "Bob"}
        record_data.record = new_rec
        client.bitable.v1.app_table_record.create.return_value = _success_resp(record_data)

        async def run():
            return await _dispatch(
                "feishu_bitable_create_record",
                {"app_token": "APP1", "table_id": "TBL1", "fields": {"Name": "Bob"}},
                client,
            )

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result["details"]["record"]["record_id"] == "rec_new"


class TestBitableBatchDeleteRecords:
    def test_batch_delete_calls_api(self):
        from src.tools.bitable_tools.register import _dispatch
        client = MagicMock()

        del_data = MagicMock()
        del_data.records = []
        client.bitable.v1.app_table_record.batch_delete.return_value = _success_resp(del_data)

        async def run():
            return await _dispatch(
                "feishu_bitable_batch_delete_records",
                {"app_token": "APP1", "table_id": "TBL1", "record_ids": ["r1", "r2"]},
                client,
            )

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result["details"]["requested"] == 2
        client.bitable.v1.app_table_record.batch_delete.assert_called_once()

    def test_batch_delete_rejects_over_500(self):
        from src.tools.bitable_tools.actions import batch_delete_records
        client = MagicMock()

        async def run():
            return await batch_delete_records(client, "APP", "TBL", ["r"] * 501)

        with pytest.raises(ValueError, match="500"):
            asyncio.get_event_loop().run_until_complete(run())


class TestBitableToolRegistration:
    def test_registers_all_11_tools(self):
        from src.tools.bitable_tools.register import register_bitable_tools

        registered = []
        api = MagicMock()
        api.register_tool = lambda name, **kwargs: registered.append(name)
        register_bitable_tools(api)
        assert len(registered) == 11
        assert "feishu_bitable_get_meta" in registered
        assert "feishu_bitable_batch_delete_records" in registered
