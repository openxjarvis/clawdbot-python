"""Register 23 feishu_task_* / feishu_tasklist_* tools.

Mirrors: clawdbot-feishu/src/task-tools/register.ts
"""
from __future__ import annotations

import logging
from typing import Any

from ..tools_common.api import json_result, error_result
from .actions import (
    create_task, get_task, update_task, delete_task,
    create_subtask, add_task_to_tasklist, remove_task_from_tasklist,
    create_tasklist, get_tasklist, list_tasklists, update_tasklist,
    delete_tasklist, add_tasklist_members, remove_tasklist_members,
    create_task_comment, list_task_comments, get_task_comment,
    update_task_comment, delete_task_comment,
    upload_task_attachment, list_task_attachments,
    get_task_attachment, delete_task_attachment,
)

logger = logging.getLogger(__name__)

_MEMBER_DESC = "Member object: {id: 'ou_xxx', type: 'user', role: 'executor'|'follower'}."
_DUE_DESC = "Due date: {timestamp: '1700000000000', is_all_day: false}."

_TOOLS: list[dict[str, Any]] = [
    # ── Tasks ──────────────────────────────────────────────────────────────
    {
        "name": "feishu_task_create",
        "description": (
            "Create a Feishu task. Important: set the requesting user as assignee so they can see it. "
            "Returns task guid for use in subsequent operations."
        ),
        "schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Task title (required)."},
                "description": {"type": "string"},
                "due": {"type": "object", "description": _DUE_DESC},
                "start": {"type": "object", "description": "Start date (same format as due)."},
                "members": {"type": "array", "items": {"type": "object"}, "description": _MEMBER_DESC},
                "tasklists": {"type": "array", "items": {"type": "object"}, "description": "Tasklists to add: [{tasklist_guid, section_guid?}]."},
                "is_milestone": {"type": "boolean"},
                "user_id_type": {"type": "string", "enum": ["open_id", "union_id", "user_id"], "default": "open_id"},
            },
            "required": ["summary"],
        },
    },
    {
        "name": "feishu_task_get",
        "description": "Get details of a task by its guid.",
        "schema": {
            "type": "object",
            "properties": {
                "task_guid": {"type": "string"},
                "user_id_type": {"type": "string", "enum": ["open_id", "union_id", "user_id"], "default": "open_id"},
            },
            "required": ["task_guid"],
        },
    },
    {
        "name": "feishu_task_update",
        "description": (
            "Update fields of an existing task. "
            "Provide a 'task' object with fields to change; update_fields is auto-inferred if omitted."
        ),
        "schema": {
            "type": "object",
            "properties": {
                "task_guid": {"type": "string"},
                "task": {
                    "type": "object",
                    "description": "Fields to update (summary, description, due, start, completed_at, is_milestone, etc.).",
                },
                "update_fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Explicit list of fields to update (auto-inferred from 'task' keys if omitted).",
                },
            },
            "required": ["task_guid", "task"],
        },
    },
    {
        "name": "feishu_task_delete",
        "description": "Delete a task permanently.",
        "schema": {"type": "object", "properties": {"task_guid": {"type": "string"}}, "required": ["task_guid"]},
    },
    {
        "name": "feishu_task_subtask_create",
        "description": "Create a subtask under a parent task. Bot can only create subtasks for tasks it created.",
        "schema": {
            "type": "object",
            "properties": {
                "task_guid": {"type": "string", "description": "Parent task guid."},
                "summary": {"type": "string"},
                "description": {"type": "string"},
                "due": {"type": "object"},
                "members": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["task_guid", "summary"],
        },
    },
    {
        "name": "feishu_task_add_tasklist",
        "description": "Add a task to a tasklist (optionally specify a section).",
        "schema": {
            "type": "object",
            "properties": {
                "task_guid": {"type": "string"},
                "tasklist_guid": {"type": "string"},
                "section_guid": {"type": "string"},
            },
            "required": ["task_guid", "tasklist_guid"],
        },
    },
    {
        "name": "feishu_task_remove_tasklist",
        "description": "Remove a task from a tasklist.",
        "schema": {
            "type": "object",
            "properties": {
                "task_guid": {"type": "string"},
                "tasklist_guid": {"type": "string"},
            },
            "required": ["task_guid", "tasklist_guid"],
        },
    },
    # ── Tasklists ───────────────────────────────────────────────────────────
    {
        "name": "feishu_tasklist_create",
        "description": "Create a new tasklist. Keep the bot as owner — add users as members instead.",
        "schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "members": {"type": "array", "items": {"type": "object"}, "description": _MEMBER_DESC},
            },
            "required": ["name"],
        },
    },
    {
        "name": "feishu_tasklist_get",
        "description": "Get details of a tasklist.",
        "schema": {"type": "object", "properties": {"tasklist_guid": {"type": "string"}}, "required": ["tasklist_guid"]},
    },
    {
        "name": "feishu_tasklist_list",
        "description": "List all tasklists accessible to the bot.",
        "schema": {
            "type": "object",
            "properties": {
                "page_size": {"type": "integer", "default": 50},
                "page_token": {"type": "string"},
            },
        },
    },
    {
        "name": "feishu_tasklist_update",
        "description": "Update a tasklist's name or settings.",
        "schema": {
            "type": "object",
            "properties": {
                "tasklist_guid": {"type": "string"},
                "tasklist": {"type": "object", "description": "Fields: name, archive_tasklist."},
                "update_fields": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["tasklist_guid", "tasklist"],
        },
    },
    {
        "name": "feishu_tasklist_delete",
        "description": "Delete a tasklist.",
        "schema": {"type": "object", "properties": {"tasklist_guid": {"type": "string"}}, "required": ["tasklist_guid"]},
    },
    {
        "name": "feishu_tasklist_add_members",
        "description": "Add members to a tasklist.",
        "schema": {
            "type": "object",
            "properties": {
                "tasklist_guid": {"type": "string"},
                "members": {"type": "array", "items": {"type": "object"}, "description": _MEMBER_DESC},
            },
            "required": ["tasklist_guid", "members"],
        },
    },
    {
        "name": "feishu_tasklist_remove_members",
        "description": "Remove members from a tasklist.",
        "schema": {
            "type": "object",
            "properties": {
                "tasklist_guid": {"type": "string"},
                "members": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["tasklist_guid", "members"],
        },
    },
    # ── Comments ─────────────────────────────────────────────────────────────
    {
        "name": "feishu_task_comment_create",
        "description": "Add a comment to a task.",
        "schema": {
            "type": "object",
            "properties": {
                "task_guid": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["task_guid", "content"],
        },
    },
    {
        "name": "feishu_task_comment_list",
        "description": "List comments on a task.",
        "schema": {
            "type": "object",
            "properties": {
                "task_guid": {"type": "string"},
                "page_size": {"type": "integer", "default": 50},
                "page_token": {"type": "string"},
            },
            "required": ["task_guid"],
        },
    },
    {
        "name": "feishu_task_comment_get",
        "description": "Get a single task comment by ID.",
        "schema": {"type": "object", "properties": {"comment_id": {"type": "string"}}, "required": ["comment_id"]},
    },
    {
        "name": "feishu_task_comment_update",
        "description": "Update the text of a task comment.",
        "schema": {
            "type": "object",
            "properties": {
                "comment_id": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["comment_id", "content"],
        },
    },
    {
        "name": "feishu_task_comment_delete",
        "description": "Delete a task comment.",
        "schema": {"type": "object", "properties": {"comment_id": {"type": "string"}}, "required": ["comment_id"]},
    },
    # ── Attachments ───────────────────────────────────────────────────────────
    {
        "name": "feishu_task_attachment_upload",
        "description": (
            "Upload a file attachment to a task. "
            "Provide file_path (local) or file_url (remote, will be downloaded). "
            "Requires task:attachment:write scope."
        ),
        "schema": {
            "type": "object",
            "properties": {
                "task_guid": {"type": "string"},
                "file_path": {"type": "string", "description": "Absolute local path to the file."},
                "file_url": {"type": "string", "description": "Public or presigned URL to download from."},
                "filename": {"type": "string", "description": "Override filename (optional)."},
            },
            "required": ["task_guid"],
        },
    },
    {
        "name": "feishu_task_attachment_list",
        "description": "List attachments on a task.",
        "schema": {
            "type": "object",
            "properties": {
                "task_guid": {"type": "string"},
                "page_size": {"type": "integer", "default": 50},
                "page_token": {"type": "string"},
            },
            "required": ["task_guid"],
        },
    },
    {
        "name": "feishu_task_attachment_get",
        "description": "Get metadata for a specific task attachment.",
        "schema": {"type": "object", "properties": {"attachment_guid": {"type": "string"}}, "required": ["attachment_guid"]},
    },
    {
        "name": "feishu_task_attachment_delete",
        "description": "Delete a task attachment.",
        "schema": {"type": "object", "properties": {"attachment_guid": {"type": "string"}}, "required": ["attachment_guid"]},
    },
]


async def _dispatch(tool_name: str, params: dict[str, Any], client: Any) -> dict[str, Any]:
    try:
        if tool_name == "feishu_task_create":
            return json_result(await create_task(client, params))
        elif tool_name == "feishu_task_get":
            return json_result(await get_task(client, params["task_guid"], params.get("user_id_type", "open_id")))
        elif tool_name == "feishu_task_update":
            return json_result(await update_task(client, params["task_guid"], params.get("task", {}), params.get("update_fields")))
        elif tool_name == "feishu_task_delete":
            return json_result(await delete_task(client, params["task_guid"]))
        elif tool_name == "feishu_task_subtask_create":
            return json_result(await create_subtask(client, params["task_guid"], params))
        elif tool_name == "feishu_task_add_tasklist":
            return json_result(await add_task_to_tasklist(client, params["task_guid"], params["tasklist_guid"], params.get("section_guid")))
        elif tool_name == "feishu_task_remove_tasklist":
            return json_result(await remove_task_from_tasklist(client, params["task_guid"], params["tasklist_guid"]))
        elif tool_name == "feishu_tasklist_create":
            return json_result(await create_tasklist(client, params))
        elif tool_name == "feishu_tasklist_get":
            return json_result(await get_tasklist(client, params["tasklist_guid"]))
        elif tool_name == "feishu_tasklist_list":
            return json_result(await list_tasklists(client, int(params.get("page_size", 50)), params.get("page_token")))
        elif tool_name == "feishu_tasklist_update":
            return json_result(await update_tasklist(client, params["tasklist_guid"], params.get("tasklist", {}), params.get("update_fields")))
        elif tool_name == "feishu_tasklist_delete":
            return json_result(await delete_tasklist(client, params["tasklist_guid"]))
        elif tool_name == "feishu_tasklist_add_members":
            return json_result(await add_tasklist_members(client, params["tasklist_guid"], params.get("members", [])))
        elif tool_name == "feishu_tasklist_remove_members":
            return json_result(await remove_tasklist_members(client, params["tasklist_guid"], params.get("members", [])))
        elif tool_name == "feishu_task_comment_create":
            return json_result(await create_task_comment(client, params["task_guid"], params["content"]))
        elif tool_name == "feishu_task_comment_list":
            return json_result(await list_task_comments(client, params["task_guid"], int(params.get("page_size", 50)), params.get("page_token")))
        elif tool_name == "feishu_task_comment_get":
            return json_result(await get_task_comment(client, params["comment_id"]))
        elif tool_name == "feishu_task_comment_update":
            return json_result(await update_task_comment(client, params["comment_id"], params["content"]))
        elif tool_name == "feishu_task_comment_delete":
            return json_result(await delete_task_comment(client, params["comment_id"]))
        elif tool_name == "feishu_task_attachment_upload":
            return json_result(await upload_task_attachment(client, params["task_guid"], file_path=params.get("file_path"), file_url=params.get("file_url"), filename=params.get("filename")))
        elif tool_name == "feishu_task_attachment_list":
            return json_result(await list_task_attachments(client, params["task_guid"], int(params.get("page_size", 50)), params.get("page_token")))
        elif tool_name == "feishu_task_attachment_get":
            return json_result(await get_task_attachment(client, params["attachment_guid"]))
        elif tool_name == "feishu_task_attachment_delete":
            return json_result(await delete_task_attachment(client, params["attachment_guid"]))
        return error_result(f"Unknown task tool: {tool_name}")
    except Exception as e:
        logger.warning("%s error: %s", tool_name, e)
        return error_result(e)


def register_task_tools(api: Any) -> None:
    """Register all 23 feishu task tools."""
    for tool_def in _TOOLS:
        name = tool_def["name"]
        def make_handler(n: str):
            async def handler(params: dict[str, Any], client: Any) -> dict[str, Any]:
                return await _dispatch(n, params, client)
            handler.__name__ = f"run_{n}"
            return handler
        api.register_tool(name=name, description=tool_def["description"], schema=tool_def["schema"], handler=make_handler(name))
    logger.info("Registered %d task tools", len(_TOOLS))
