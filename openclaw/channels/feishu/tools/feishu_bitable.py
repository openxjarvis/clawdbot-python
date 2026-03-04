"""feishu_bitable tool — Feishu multidimensional tables (Bitable) operations.

Mirrors TypeScript: extensions/feishu/src/bitable.ts
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

TOOL_NAME = "feishu_bitable"
TOOL_DESCRIPTION = (
    "Access Feishu Bitable (multidimensional tables): list tables, query records, "
    "create/update/delete records."
)
TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["list_tables", "list_records", "get_record", "create_record", "update_record", "delete_record"],
            "description": "Action to perform.",
        },
        "app_token": {
            "type": "string",
            "description": "Bitable app token.",
        },
        "table_id": {
            "type": "string",
            "description": "Table ID within the Bitable.",
        },
        "record_id": {
            "type": "string",
            "description": "Record ID for get/update/delete.",
        },
        "fields": {
            "type": "object",
            "description": "Record fields dict for create/update.",
        },
        "filter": {
            "type": "string",
            "description": "Filter expression for list_records.",
        },
        "page_token": {
            "type": "string",
            "description": "Pagination token.",
        },
        "page_size": {
            "type": "integer",
            "description": "Number of records per page (max 100).",
        },
    },
    "required": ["action", "app_token"],
}


async def run_feishu_bitable(
    params: dict[str, Any],
    client: Any,
) -> dict[str, Any]:
    """Execute feishu_bitable tool call."""
    action = params.get("action", "list_tables")
    app_token = params.get("app_token", "")
    table_id = params.get("table_id", "")
    loop = asyncio.get_running_loop()

    if action == "list_tables":
        try:
            from lark_oapi.api.bitable.v1 import ListAppTableRequest

            request = ListAppTableRequest.builder().app_token(app_token).build()
            response = await loop.run_in_executor(
                None, lambda: client.bitable.v1.app_table.list(request)
            )
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            tables = []
            for t in (response.data.items or []):
                tables.append({
                    "table_id": getattr(t, "table_id", ""),
                    "name": getattr(t, "name", ""),
                    "revision": getattr(t, "revision", 0),
                })
            return {"tables": tables}
        except Exception as e:
            return {"error": str(e)}

    elif action == "list_records":
        if not table_id:
            return {"error": "table_id is required for list_records"}
        page_token = params.get("page_token", "")
        page_size = min(int(params.get("page_size", 20)), 100)
        filter_expr = params.get("filter", "")
        try:
            from lark_oapi.api.bitable.v1 import ListAppTableRecordRequest

            builder = (
                ListAppTableRecordRequest.builder()
                .app_token(app_token)
                .table_id(table_id)
                .page_size(page_size)
            )
            if page_token:
                builder = builder.page_token(page_token)
            if filter_expr:
                builder = builder.filter(filter_expr)
            request = builder.build()
            response = await loop.run_in_executor(
                None, lambda: client.bitable.v1.app_table_record.list(request)
            )
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            records = []
            for r in (response.data.items or []):
                records.append({
                    "record_id": getattr(r, "record_id", ""),
                    "fields": getattr(r, "fields", {}),
                })
            return {
                "records": records,
                "has_more": getattr(response.data, "has_more", False),
                "page_token": getattr(response.data, "page_token", ""),
                "total": getattr(response.data, "total", len(records)),
            }
        except Exception as e:
            return {"error": str(e)}

    elif action == "get_record":
        if not table_id or not params.get("record_id"):
            return {"error": "table_id and record_id are required"}
        record_id = params["record_id"]
        try:
            from lark_oapi.api.bitable.v1 import GetAppTableRecordRequest

            request = (
                GetAppTableRecordRequest.builder()
                .app_token(app_token)
                .table_id(table_id)
                .record_id(record_id)
                .build()
            )
            response = await loop.run_in_executor(
                None, lambda: client.bitable.v1.app_table_record.get(request)
            )
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            r = response.data.record
            return {
                "record_id": getattr(r, "record_id", ""),
                "fields": getattr(r, "fields", {}),
            }
        except Exception as e:
            return {"error": str(e)}

    elif action == "create_record":
        if not table_id:
            return {"error": "table_id is required"}
        fields = params.get("fields", {})
        try:
            from lark_oapi.api.bitable.v1 import CreateAppTableRecordRequest, CreateAppTableRecordRequestBody
            from lark_oapi.api.bitable.v1.model import AppTableRecord

            record = AppTableRecord.builder().fields(fields).build()
            request = (
                CreateAppTableRecordRequest.builder()
                .app_token(app_token)
                .table_id(table_id)
                .request_body(
                    CreateAppTableRecordRequestBody.builder()
                    .fields(fields)
                    .build()
                )
                .build()
            )
            response = await loop.run_in_executor(
                None, lambda: client.bitable.v1.app_table_record.create(request)
            )
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            r = response.data.record
            return {
                "record_id": getattr(r, "record_id", ""),
                "fields": getattr(r, "fields", {}),
            }
        except Exception as e:
            return {"error": str(e)}

    elif action == "update_record":
        if not table_id or not params.get("record_id"):
            return {"error": "table_id and record_id are required"}
        record_id = params["record_id"]
        fields = params.get("fields", {})
        try:
            from lark_oapi.api.bitable.v1 import UpdateAppTableRecordRequest, UpdateAppTableRecordRequestBody

            request = (
                UpdateAppTableRecordRequest.builder()
                .app_token(app_token)
                .table_id(table_id)
                .record_id(record_id)
                .request_body(
                    UpdateAppTableRecordRequestBody.builder()
                    .fields(fields)
                    .build()
                )
                .build()
            )
            response = await loop.run_in_executor(
                None, lambda: client.bitable.v1.app_table_record.update(request)
            )
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            return {"status": "updated", "record_id": record_id}
        except Exception as e:
            return {"error": str(e)}

    elif action == "delete_record":
        if not table_id or not params.get("record_id"):
            return {"error": "table_id and record_id are required"}
        record_id = params["record_id"]
        try:
            from lark_oapi.api.bitable.v1 import DeleteAppTableRecordRequest

            request = (
                DeleteAppTableRecordRequest.builder()
                .app_token(app_token)
                .table_id(table_id)
                .record_id(record_id)
                .build()
            )
            response = await loop.run_in_executor(
                None, lambda: client.bitable.v1.app_table_record.delete(request)
            )
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            return {"status": "deleted", "record_id": record_id}
        except Exception as e:
            return {"error": str(e)}

    return {"error": f"Unknown action: {action}"}
