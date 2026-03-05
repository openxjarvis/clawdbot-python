"""Bitable field and record action implementations.

Mirrors: clawdbot-feishu/src/bitable-tools/actions.ts

Retry policy: codes [1254607, 1255040, 1254290, 1254291], backoff [350, 900, 1800] ms.
"""
from __future__ import annotations

import asyncio
from typing import Any

from ..tools_common.api import run_feishu_api_call

_BITABLE_RETRYABLE_CODES = [1254607, 1255040, 1254290, 1254291]
_BITABLE_BACKOFF_MS = [350, 900, 1800]

# Field type id → human-readable name mapping
_FIELD_TYPE_NAMES: dict[int, str] = {
    1: "Text", 2: "Number", 3: "SingleSelect", 4: "MultiSelect",
    5: "DateTime", 7: "Checkbox", 11: "User", 13: "Phone",
    15: "URL", 17: "Attachment", 18: "SingleLink", 19: "Lookup",
    20: "Formula", 21: "DuplexLink", 22: "Location", 23: "GroupChat",
    1001: "CreatedTime", 1002: "ModifiedTime", 1003: "CreatedUser",
    1004: "ModifiedUser", 1005: "AutoNumber",
}


def _format_field(f: Any) -> dict[str, Any]:
    type_id = getattr(f, "type", 0) or 0
    return {
        "field_id": getattr(f, "field_id", ""),
        "field_name": getattr(f, "field_name", ""),
        "type": type_id,
        "type_name": _FIELD_TYPE_NAMES.get(type_id, f"Unknown({type_id})"),
        "is_primary": getattr(f, "is_primary", False),
        "description": getattr(getattr(f, "description", None), "text", "") if getattr(f, "description", None) else "",
    }


def _format_record(r: Any) -> dict[str, Any]:
    return {
        "record_id": getattr(r, "record_id", ""),
        "fields": getattr(r, "fields", {}) or {},
    }


async def list_fields(client: Any, app_token: str, table_id: str) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.bitable.v1 import ListAppTableFieldRequest

    req = ListAppTableFieldRequest.builder().app_token(app_token).table_id(table_id).build()
    resp = await run_feishu_api_call(
        "bitable.app_table_field.list",
        lambda: client.bitable.v1.app_table_field.list(req),
        retryable_codes=_BITABLE_RETRYABLE_CODES,
        backoff_ms=_BITABLE_BACKOFF_MS,
    )
    fields = [_format_field(f) for f in (resp.data.items or [])]
    return {"fields": fields, "total": len(fields)}


async def create_field(
    client: Any, app_token: str, table_id: str,
    field_name: str, field_type: int,
    property_: dict | None = None, description: str | None = None, ui_type: str | None = None,
) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.bitable.v1 import CreateAppTableFieldRequest
    from lark_oapi.api.bitable.v1.model import AppTableField

    builder = AppTableField.builder().field_name(field_name).type(field_type)
    if property_:
        builder = builder.property(property_)
    if ui_type:
        builder = builder.ui_type(ui_type)
    field = builder.build()

    req = (
        CreateAppTableFieldRequest.builder()
        .app_token(app_token).table_id(table_id)
        .request_body(field)
        .build()
    )
    resp = await run_feishu_api_call(
        "bitable.app_table_field.create",
        lambda: client.bitable.v1.app_table_field.create(req),
        retryable_codes=_BITABLE_RETRYABLE_CODES,
        backoff_ms=_BITABLE_BACKOFF_MS,
    )
    return {"field": _format_field(resp.data.field)}


async def update_field(
    client: Any, app_token: str, table_id: str, field_id: str,
    field_name: str, field_type: int,
    property_: dict | None = None, description: str | None = None, ui_type: str | None = None,
) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.bitable.v1 import UpdateAppTableFieldRequest
    from lark_oapi.api.bitable.v1.model import AppTableField

    builder = AppTableField.builder().field_name(field_name).type(field_type)
    if property_:
        builder = builder.property(property_)
    if ui_type:
        builder = builder.ui_type(ui_type)
    field = builder.build()

    req = (
        UpdateAppTableFieldRequest.builder()
        .app_token(app_token).table_id(table_id).field_id(field_id)
        .request_body(field)
        .build()
    )
    resp = await run_feishu_api_call(
        "bitable.app_table_field.update",
        lambda: client.bitable.v1.app_table_field.update(req),
        retryable_codes=_BITABLE_RETRYABLE_CODES,
        backoff_ms=_BITABLE_BACKOFF_MS,
    )
    return {"field": _format_field(resp.data.field)}


async def delete_field(client: Any, app_token: str, table_id: str, field_id: str) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.bitable.v1 import DeleteAppTableFieldRequest

    req = DeleteAppTableFieldRequest.builder().app_token(app_token).table_id(table_id).field_id(field_id).build()
    resp = await run_feishu_api_call(
        "bitable.app_table_field.delete",
        lambda: client.bitable.v1.app_table_field.delete(req),
        retryable_codes=_BITABLE_RETRYABLE_CODES,
        backoff_ms=_BITABLE_BACKOFF_MS,
    )
    return {"success": True, "field_id": field_id, "deleted": getattr(resp.data, "deleted", True)}


async def list_records(
    client: Any, app_token: str, table_id: str,
    page_size: int = 100, page_token: str | None = None,
) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.bitable.v1 import ListAppTableRecordRequest

    builder = (
        ListAppTableRecordRequest.builder()
        .app_token(app_token).table_id(table_id)
        .page_size(min(page_size, 500))
    )
    if page_token:
        builder = builder.page_token(page_token)
    resp = await run_feishu_api_call(
        "bitable.app_table_record.list",
        lambda: client.bitable.v1.app_table_record.list(builder.build()),
        retryable_codes=_BITABLE_RETRYABLE_CODES,
        backoff_ms=_BITABLE_BACKOFF_MS,
    )
    records = [_format_record(r) for r in (resp.data.items or [])]
    return {
        "records": records,
        "has_more": getattr(resp.data, "has_more", False),
        "page_token": getattr(resp.data, "page_token", "") or "",
        "total": getattr(resp.data, "total", len(records)),
    }


async def get_record(client: Any, app_token: str, table_id: str, record_id: str) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.bitable.v1 import GetAppTableRecordRequest

    req = GetAppTableRecordRequest.builder().app_token(app_token).table_id(table_id).record_id(record_id).build()
    resp = await run_feishu_api_call(
        "bitable.app_table_record.get",
        lambda: client.bitable.v1.app_table_record.get(req),
        retryable_codes=_BITABLE_RETRYABLE_CODES,
        backoff_ms=_BITABLE_BACKOFF_MS,
    )
    return {"record": _format_record(resp.data.record)}


async def create_record(client: Any, app_token: str, table_id: str, fields: dict) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.bitable.v1 import CreateAppTableRecordRequest
    from lark_oapi.api.bitable.v1.model import AppTableRecord

    record = AppTableRecord.builder().fields(fields).build()
    req = (
        CreateAppTableRecordRequest.builder()
        .app_token(app_token).table_id(table_id)
        .request_body(record)
        .build()
    )
    resp = await run_feishu_api_call(
        "bitable.app_table_record.create",
        lambda: client.bitable.v1.app_table_record.create(req),
        retryable_codes=_BITABLE_RETRYABLE_CODES,
        backoff_ms=_BITABLE_BACKOFF_MS,
    )
    return {"record": _format_record(resp.data.record)}


async def update_record(client: Any, app_token: str, table_id: str, record_id: str, fields: dict) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.bitable.v1 import UpdateAppTableRecordRequest
    from lark_oapi.api.bitable.v1.model import AppTableRecord

    record = AppTableRecord.builder().fields(fields).build()
    req = (
        UpdateAppTableRecordRequest.builder()
        .app_token(app_token).table_id(table_id).record_id(record_id)
        .request_body(record)
        .build()
    )
    resp = await run_feishu_api_call(
        "bitable.app_table_record.update",
        lambda: client.bitable.v1.app_table_record.update(req),
        retryable_codes=_BITABLE_RETRYABLE_CODES,
        backoff_ms=_BITABLE_BACKOFF_MS,
    )
    return {"record": _format_record(resp.data.record)}


async def delete_record(client: Any, app_token: str, table_id: str, record_id: str) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.bitable.v1 import DeleteAppTableRecordRequest

    req = DeleteAppTableRecordRequest.builder().app_token(app_token).table_id(table_id).record_id(record_id).build()
    resp = await run_feishu_api_call(
        "bitable.app_table_record.delete",
        lambda: client.bitable.v1.app_table_record.delete(req),
        retryable_codes=_BITABLE_RETRYABLE_CODES,
        backoff_ms=_BITABLE_BACKOFF_MS,
    )
    return {"success": True, "record_id": record_id, "deleted": getattr(resp.data, "deleted", True)}


async def batch_delete_records(client: Any, app_token: str, table_id: str, record_ids: list[str]) -> dict[str, Any]:
    """Batch delete up to 500 records in a single call."""
    if len(record_ids) > 500:
        raise ValueError("batch_delete_records supports at most 500 record_ids per call")
    loop = asyncio.get_running_loop()
    from lark_oapi.api.bitable.v1 import BatchDeleteAppTableRecordRequest, BatchDeleteAppTableRecordRequestBody

    req = (
        BatchDeleteAppTableRecordRequest.builder()
        .app_token(app_token).table_id(table_id)
        .request_body(BatchDeleteAppTableRecordRequestBody.builder().records(record_ids).build())
        .build()
    )
    resp = await run_feishu_api_call(
        "bitable.app_table_record.batch_delete",
        lambda: client.bitable.v1.app_table_record.batch_delete(req),
        retryable_codes=_BITABLE_RETRYABLE_CODES,
        backoff_ms=_BITABLE_BACKOFF_MS,
    )
    results = getattr(resp.data, "records", None) or []
    return {
        "requested": len(record_ids),
        "deleted": len(results),
        "results": results,
    }
