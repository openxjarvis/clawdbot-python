"""Register 11 individual feishu_bitable_* tools.

Mirrors: clawdbot-feishu/src/bitable-tools/register.ts
"""
from __future__ import annotations

import logging
from typing import Any

from ..tools_common.api import json_result, error_result
from .meta import get_bitable_meta
from .actions import (
    list_fields, create_field, update_field, delete_field,
    list_records, get_record, create_record, update_record, delete_record, batch_delete_records,
)

logger = logging.getLogger(__name__)

_FIELD_TYPE_DESC = (
    "Field type id: 1=Text, 2=Number, 3=SingleSelect, 4=MultiSelect, 5=DateTime, "
    "7=Checkbox, 11=User, 15=URL, 17=Attachment. "
    "Field value formats — Text:'string', Number:123, SingleSelect:'Option', "
    "MultiSelect:['A','B'], DateTime:timestamp_ms, User:[{id:'ou_xxx'}], URL:{text:'...',link:'https://...'}."
)

# ── Tool definitions ────────────────────────────────────────────────────────

_TOOLS: list[dict[str, Any]] = [
    {
        "name": "feishu_bitable_get_meta",
        "description": (
            "Parse a Feishu Bitable URL to resolve app_token and list tables. "
            "Always call this first when given a Bitable URL before using other feishu_bitable_* tools."
        ),
        "schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Full Feishu Bitable URL (/base/... or /wiki/...)."},
            },
            "required": ["url"],
        },
    },
    {
        "name": "feishu_bitable_list_fields",
        "description": "List all fields (columns) in a Bitable table with their types.",
        "schema": {
            "type": "object",
            "properties": {
                "app_token": {"type": "string", "description": "Bitable app token."},
                "table_id": {"type": "string", "description": "Table ID."},
            },
            "required": ["app_token", "table_id"],
        },
    },
    {
        "name": "feishu_bitable_create_field",
        "description": f"Create a new field (column) in a Bitable table. {_FIELD_TYPE_DESC}",
        "schema": {
            "type": "object",
            "properties": {
                "app_token": {"type": "string"},
                "table_id": {"type": "string"},
                "field_name": {"type": "string", "description": "Name for the new field."},
                "type": {"type": "integer", "description": "Field type id (see description)."},
                "property": {"type": "object", "description": "Field-type-specific property config."},
                "ui_type": {"type": "string", "description": "Optional UI type override."},
            },
            "required": ["app_token", "table_id", "field_name", "type"],
        },
    },
    {
        "name": "feishu_bitable_update_field",
        "description": "Update an existing field's name, type, or properties.",
        "schema": {
            "type": "object",
            "properties": {
                "app_token": {"type": "string"},
                "table_id": {"type": "string"},
                "field_id": {"type": "string", "description": "ID of the field to update."},
                "field_name": {"type": "string"},
                "type": {"type": "integer"},
                "property": {"type": "object"},
                "ui_type": {"type": "string"},
            },
            "required": ["app_token", "table_id", "field_id", "field_name", "type"],
        },
    },
    {
        "name": "feishu_bitable_delete_field",
        "description": "Delete a field from a Bitable table. Irreversible.",
        "schema": {
            "type": "object",
            "properties": {
                "app_token": {"type": "string"},
                "table_id": {"type": "string"},
                "field_id": {"type": "string"},
            },
            "required": ["app_token", "table_id", "field_id"],
        },
    },
    {
        "name": "feishu_bitable_list_records",
        "description": "List records in a Bitable table with optional pagination.",
        "schema": {
            "type": "object",
            "properties": {
                "app_token": {"type": "string"},
                "table_id": {"type": "string"},
                "page_size": {"type": "integer", "description": "Records per page (1–500, default 100)."},
                "page_token": {"type": "string", "description": "Pagination cursor."},
            },
            "required": ["app_token", "table_id"],
        },
    },
    {
        "name": "feishu_bitable_get_record",
        "description": "Get a single record by ID.",
        "schema": {
            "type": "object",
            "properties": {
                "app_token": {"type": "string"},
                "table_id": {"type": "string"},
                "record_id": {"type": "string"},
            },
            "required": ["app_token", "table_id", "record_id"],
        },
    },
    {
        "name": "feishu_bitable_create_record",
        "description": f"Create a new record in a Bitable table. {_FIELD_TYPE_DESC}",
        "schema": {
            "type": "object",
            "properties": {
                "app_token": {"type": "string"},
                "table_id": {"type": "string"},
                "fields": {"type": "object", "description": "Map of field_name → value."},
            },
            "required": ["app_token", "table_id", "fields"],
        },
    },
    {
        "name": "feishu_bitable_update_record",
        "description": "Update fields of an existing record.",
        "schema": {
            "type": "object",
            "properties": {
                "app_token": {"type": "string"},
                "table_id": {"type": "string"},
                "record_id": {"type": "string"},
                "fields": {"type": "object", "description": "Map of field_name → new value."},
            },
            "required": ["app_token", "table_id", "record_id", "fields"],
        },
    },
    {
        "name": "feishu_bitable_delete_record",
        "description": "Delete a single record by ID.",
        "schema": {
            "type": "object",
            "properties": {
                "app_token": {"type": "string"},
                "table_id": {"type": "string"},
                "record_id": {"type": "string"},
            },
            "required": ["app_token", "table_id", "record_id"],
        },
    },
    {
        "name": "feishu_bitable_batch_delete_records",
        "description": "Batch delete up to 500 records in a single call.",
        "schema": {
            "type": "object",
            "properties": {
                "app_token": {"type": "string"},
                "table_id": {"type": "string"},
                "record_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of record IDs to delete (max 500).",
                    "maxItems": 500,
                },
            },
            "required": ["app_token", "table_id", "record_ids"],
        },
    },
]


async def _dispatch(tool_name: str, params: dict[str, Any], client: Any) -> dict[str, Any]:
    """Route a tool call to the correct action function."""
    app_token = params.get("app_token", "")
    table_id = params.get("table_id", "")
    try:
        if tool_name == "feishu_bitable_get_meta":
            url = params.get("url", "")
            if not url:
                return error_result("url is required")
            return json_result(await get_bitable_meta(client, url))

        elif tool_name == "feishu_bitable_list_fields":
            return json_result(await list_fields(client, app_token, table_id))

        elif tool_name == "feishu_bitable_create_field":
            return json_result(await create_field(
                client, app_token, table_id,
                field_name=params.get("field_name", ""),
                field_type=int(params.get("type", 1)),
                property_=params.get("property"),
                ui_type=params.get("ui_type"),
            ))

        elif tool_name == "feishu_bitable_update_field":
            return json_result(await update_field(
                client, app_token, table_id,
                field_id=params.get("field_id", ""),
                field_name=params.get("field_name", ""),
                field_type=int(params.get("type", 1)),
                property_=params.get("property"),
                ui_type=params.get("ui_type"),
            ))

        elif tool_name == "feishu_bitable_delete_field":
            return json_result(await delete_field(client, app_token, table_id, params.get("field_id", "")))

        elif tool_name == "feishu_bitable_list_records":
            return json_result(await list_records(
                client, app_token, table_id,
                page_size=int(params.get("page_size", 100)),
                page_token=params.get("page_token"),
            ))

        elif tool_name == "feishu_bitable_get_record":
            return json_result(await get_record(client, app_token, table_id, params.get("record_id", "")))

        elif tool_name == "feishu_bitable_create_record":
            return json_result(await create_record(client, app_token, table_id, params.get("fields", {})))

        elif tool_name == "feishu_bitable_update_record":
            return json_result(await update_record(client, app_token, table_id, params.get("record_id", ""), params.get("fields", {})))

        elif tool_name == "feishu_bitable_delete_record":
            return json_result(await delete_record(client, app_token, table_id, params.get("record_id", "")))

        elif tool_name == "feishu_bitable_batch_delete_records":
            return json_result(await batch_delete_records(client, app_token, table_id, params.get("record_ids", [])))

        return error_result(f"Unknown bitable tool: {tool_name}")
    except Exception as e:
        logger.warning("%s error: %s", tool_name, e)
        return error_result(e)


def register_bitable_tools(api: Any) -> None:
    """Register all 11 feishu_bitable_* tools."""
    for tool_def in _TOOLS:
        name = tool_def["name"]
        # Capture name in closure
        def make_handler(n: str):
            async def handler(params: dict[str, Any], client: Any) -> dict[str, Any]:
                return await _dispatch(n, params, client)
            handler.__name__ = f"run_{n}"
            return handler

        api.register_tool(
            name=name,
            description=tool_def["description"],
            schema=tool_def["schema"],
            handler=make_handler(name),
        )
    logger.info("Registered %d bitable tools", len(_TOOLS))
