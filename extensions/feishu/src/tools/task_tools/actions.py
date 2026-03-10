"""Task v2 API action implementations.

Mirrors: clawdbot-feishu/src/task-tools/actions.ts

Covers: tasks, subtasks, tasklists, task-tasklist links,
        task comments, task attachments.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from typing import Any

from .constants import TASK_UPDATE_FIELDS, TASKLIST_UPDATE_FIELDS


def _format_task(t: Any) -> dict[str, Any]:
    if t is None:
        return {}
    return {
        "guid": getattr(t, "guid", ""),
        "task_id": getattr(t, "task_id", ""),
        "summary": getattr(t, "summary", ""),
        "description": getattr(t, "description", ""),
        "completed_at": getattr(t, "completed_at", ""),
        "due": _safe_dict(getattr(t, "due", None)),
        "start": _safe_dict(getattr(t, "start", None)),
        "is_milestone": getattr(t, "is_milestone", False),
        "url": getattr(t, "url", ""),
        "created_at": getattr(t, "created_at", ""),
        "updated_at": getattr(t, "updated_at", ""),
    }


def _format_tasklist(tl: Any) -> dict[str, Any]:
    if tl is None:
        return {}
    return {
        "guid": getattr(tl, "guid", ""),
        "name": getattr(tl, "name", ""),
        "url": getattr(tl, "url", ""),
        "created_at": getattr(tl, "created_at", ""),
        "updated_at": getattr(tl, "updated_at", ""),
    }


def _format_attachment(a: Any) -> dict[str, Any]:
    if a is None:
        return {}
    return {
        "guid": getattr(a, "guid", ""),
        "name": getattr(a, "name", ""),
        "size": getattr(a, "size", 0),
        "mime_type": getattr(a, "mime_type", ""),
        "url": getattr(a, "url", ""),
        "created_at": getattr(a, "created_at", ""),
    }


def _format_comment(c: Any) -> dict[str, Any]:
    if c is None:
        return {}
    return {
        "id": getattr(c, "id", ""),
        "content": getattr(c, "content", ""),
        "created_at": getattr(c, "created_at", ""),
        "updated_at": getattr(c, "updated_at", ""),
    }


def _safe_dict(obj: Any) -> dict | None:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj
    return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")} if hasattr(obj, "__dict__") else None


def _infer_update_fields(task_dict: dict, allowed: list[str]) -> list[str]:
    """Return list of field names present in task_dict that are in allowed."""
    return [f for f in allowed if f in task_dict]


# ── Tasks ───────────────────────────────────────────────────────────────────

async def create_task(client: Any, params: dict) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.task.v2 import CreateTaskRequest
    from lark_oapi.api.task.v2.model import InputTask

    task = InputTask.builder().summary(params.get("summary", ""))
    for field in ["description", "is_milestone", "repeat_rule", "extra"]:
        if field in params and hasattr(task, field):
            task = getattr(task, field)(params[field])
    for field in ["due", "start"]:
        if field in params and hasattr(task, field):
            task = getattr(task, field)(params[field])
    if params.get("members") and hasattr(task, "members"):
        task = task.members(params["members"])
    task_obj = task.build()

    uid_type = params.get("user_id_type", "open_id")
    req = (
        CreateTaskRequest.builder()
        .user_id_type(uid_type)
        .request_body(task_obj)
        .build()
    )
    resp = await loop.run_in_executor(None, lambda: client.task.v2.task.create(req))
    if not resp.success():
        raise RuntimeError(f"task.create failed: {resp.msg}, code={resp.code}")
    return {"task": _format_task(resp.data.task)}


async def get_task(client: Any, task_guid: str, user_id_type: str = "open_id") -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.task.v2 import GetTaskRequest

    req = GetTaskRequest.builder().task_guid(task_guid).user_id_type(user_id_type).build()
    resp = await loop.run_in_executor(None, lambda: client.task.v2.task.get(req))
    if not resp.success():
        raise RuntimeError(f"task.get failed: {resp.msg}, code={resp.code}")
    return {"task": _format_task(resp.data.task)}


async def update_task(client: Any, task_guid: str, task_fields: dict, update_fields: list[str] | None = None) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.task.v2 import PatchTaskRequest, PatchTaskRequestBody
    from lark_oapi.api.task.v2.model import InputTask

    inferred = update_fields or _infer_update_fields(task_fields, TASK_UPDATE_FIELDS)

    task = InputTask.builder()
    for k, v in task_fields.items():
        if hasattr(task, k):
            task = getattr(task, k)(v)
    task_obj = task.build()

    req = (
        PatchTaskRequest.builder()
        .task_guid(task_guid)
        .request_body(
            PatchTaskRequestBody.builder().task(task_obj).update_fields(inferred).build()
        )
        .build()
    )
    resp = await loop.run_in_executor(None, lambda: client.task.v2.task.patch(req))
    if not resp.success():
        raise RuntimeError(f"task.patch failed: {resp.msg}, code={resp.code}")
    return {"task": _format_task(resp.data.task), "update_fields": inferred}


async def delete_task(client: Any, task_guid: str) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.task.v2 import DeleteTaskRequest

    req = DeleteTaskRequest.builder().task_guid(task_guid).build()
    resp = await loop.run_in_executor(None, lambda: client.task.v2.task.delete(req))
    if not resp.success():
        raise RuntimeError(f"task.delete failed: {resp.msg}, code={resp.code}")
    return {"success": True, "task_guid": task_guid}


async def create_subtask(client: Any, parent_task_guid: str, params: dict) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.task.v2 import CreateTaskSubtaskRequest
    from lark_oapi.api.task.v2.model import InputTask

    task = InputTask.builder().summary(params.get("summary", ""))
    for field in ["description", "is_milestone"]:
        if field in params and hasattr(task, field):
            task = getattr(task, field)(params[field])
    for field in ["due", "start"]:
        if field in params and hasattr(task, field):
            task = getattr(task, field)(params[field])

    req = (
        CreateTaskSubtaskRequest.builder()
        .task_guid(parent_task_guid)
        .request_body(task.build())
        .build()
    )
    resp = await loop.run_in_executor(None, lambda: client.task.v2.task_subtask.create(req))
    if not resp.success():
        raise RuntimeError(f"task_subtask.create failed: {resp.msg}, code={resp.code}")
    return {"subtask": _format_task(resp.data.task)}


async def add_task_to_tasklist(client: Any, task_guid: str, tasklist_guid: str, section_guid: str | None = None) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.task.v2 import AddTasklistTaskRequest, AddTasklistTaskRequestBody

    builder = AddTasklistTaskRequestBody.builder().tasklist_guid(tasklist_guid)
    if section_guid:
        builder = builder.section_guid(section_guid)
    req = AddTasklistTaskRequest.builder().task_guid(task_guid).request_body(builder.build()).build()
    resp = await loop.run_in_executor(None, lambda: client.task.v2.task.add_tasklist(req))
    if not resp.success():
        raise RuntimeError(f"task.add_tasklist failed: {resp.msg}, code={resp.code}")
    return {"task": _format_task(resp.data.task)}


async def remove_task_from_tasklist(client: Any, task_guid: str, tasklist_guid: str) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.task.v2 import RemoveTasklistTaskRequest, RemoveTasklistTaskRequestBody

    req = RemoveTasklistTaskRequest.builder().task_guid(task_guid).request_body(
        RemoveTasklistTaskRequestBody.builder().tasklist_guid(tasklist_guid).build()
    ).build()
    resp = await loop.run_in_executor(None, lambda: client.task.v2.task.remove_tasklist(req))
    if not resp.success():
        raise RuntimeError(f"task.remove_tasklist failed: {resp.msg}, code={resp.code}")
    return {"task": _format_task(resp.data.task)}


# ── Tasklists ───────────────────────────────────────────────────────────────

async def create_tasklist(client: Any, params: dict) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.task.v2 import CreateTasklistRequest
    from lark_oapi.api.task.v2.model import InputTasklist

    tl_builder = InputTasklist.builder().name(params.get("name", ""))
    if params.get("members") and hasattr(tl_builder, "members"):
        tl_builder = tl_builder.members(params["members"])
    req = (
        CreateTasklistRequest.builder()
        .request_body(tl_builder.build())
        .build()
    )
    resp = await loop.run_in_executor(None, lambda: client.task.v2.tasklist.create(req))
    if not resp.success():
        raise RuntimeError(f"tasklist.create failed: {resp.msg}, code={resp.code}")
    return {"tasklist": _format_tasklist(resp.data.tasklist)}


async def get_tasklist(client: Any, tasklist_guid: str) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.task.v2 import GetTasklistRequest

    req = GetTasklistRequest.builder().tasklist_guid(tasklist_guid).build()
    resp = await loop.run_in_executor(None, lambda: client.task.v2.tasklist.get(req))
    if not resp.success():
        raise RuntimeError(f"tasklist.get failed: {resp.msg}, code={resp.code}")
    return {"tasklist": _format_tasklist(resp.data.tasklist)}


async def list_tasklists(client: Any, page_size: int = 50, page_token: str | None = None) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.task.v2 import ListTasklistRequest

    builder = ListTasklistRequest.builder().page_size(min(page_size, 200))
    if page_token:
        builder = builder.page_token(page_token)
    resp = await loop.run_in_executor(None, lambda: client.task.v2.tasklist.list(builder.build()))
    if not resp.success():
        raise RuntimeError(f"tasklist.list failed: {resp.msg}, code={resp.code}")
    items = [_format_tasklist(tl) for tl in (resp.data.items or [])]
    return {
        "items": items,
        "has_more": getattr(resp.data, "has_more", False),
        "page_token": getattr(resp.data, "page_token", "") or "",
    }


async def update_tasklist(client: Any, tasklist_guid: str, tasklist_fields: dict, update_fields: list[str] | None = None) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.task.v2 import PatchTasklistRequest, PatchTasklistRequestBody
    from lark_oapi.api.task.v2.model import InputTasklist

    inferred = update_fields or _infer_update_fields(tasklist_fields, TASKLIST_UPDATE_FIELDS)
    tl = InputTasklist.builder()
    for k, v in tasklist_fields.items():
        if hasattr(tl, k):
            tl = getattr(tl, k)(v)
    req = (
        PatchTasklistRequest.builder()
        .tasklist_guid(tasklist_guid)
        .request_body(PatchTasklistRequestBody.builder().tasklist(tl.build()).update_fields(inferred).build())
        .build()
    )
    resp = await loop.run_in_executor(None, lambda: client.task.v2.tasklist.patch(req))
    if not resp.success():
        raise RuntimeError(f"tasklist.patch failed: {resp.msg}, code={resp.code}")
    return {"tasklist": _format_tasklist(resp.data.tasklist), "update_fields": inferred}


async def delete_tasklist(client: Any, tasklist_guid: str) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.task.v2 import DeleteTasklistRequest

    req = DeleteTasklistRequest.builder().tasklist_guid(tasklist_guid).build()
    resp = await loop.run_in_executor(None, lambda: client.task.v2.tasklist.delete(req))
    if not resp.success():
        raise RuntimeError(f"tasklist.delete failed: {resp.msg}, code={resp.code}")
    return {"success": True, "tasklist_guid": tasklist_guid}


async def add_tasklist_members(client: Any, tasklist_guid: str, members: list[dict]) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.task.v2 import AddMembersTasklistRequest, AddMembersTasklistRequestBody

    req = AddMembersTasklistRequest.builder().tasklist_guid(tasklist_guid).request_body(
        AddMembersTasklistRequestBody.builder().members(members).build()
    ).build()
    resp = await loop.run_in_executor(None, lambda: client.task.v2.tasklist.add_members(req))
    if not resp.success():
        raise RuntimeError(f"tasklist.add_members failed: {resp.msg}, code={resp.code}")
    return {"tasklist": _format_tasklist(resp.data.tasklist)}


async def remove_tasklist_members(client: Any, tasklist_guid: str, members: list[dict]) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.task.v2 import RemoveMembersTasklistRequest, RemoveMembersTasklistRequestBody

    req = RemoveMembersTasklistRequest.builder().tasklist_guid(tasklist_guid).request_body(
        RemoveMembersTasklistRequestBody.builder().members(members).build()
    ).build()
    resp = await loop.run_in_executor(None, lambda: client.task.v2.tasklist.remove_members(req))
    if not resp.success():
        raise RuntimeError(f"tasklist.remove_members failed: {resp.msg}, code={resp.code}")
    return {"tasklist": _format_tasklist(resp.data.tasklist)}


# ── Comments ────────────────────────────────────────────────────────────────

async def create_task_comment(client: Any, task_guid: str, content: str) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.task.v2 import CreateCommentRequest
    from lark_oapi.api.task.v2.model import InputComment

    comment = (
        InputComment.builder()
        .content(content)
        .resource_type("task")
        .resource_id(task_guid)
        .build()
    )
    req = CreateCommentRequest.builder().request_body(comment).build()
    resp = await loop.run_in_executor(None, lambda: client.task.v2.comment.create(req))
    if not resp.success():
        raise RuntimeError(f"comment.create failed: {resp.msg}, code={resp.code}")
    return {"comment": _format_comment(resp.data.comment)}


async def list_task_comments(client: Any, task_guid: str, page_size: int = 50, page_token: str | None = None) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.task.v2 import ListCommentRequest

    builder = (
        ListCommentRequest.builder()
        .resource_type("task")
        .resource_id(task_guid)
        .page_size(min(page_size, 100))
    )
    if page_token:
        builder = builder.page_token(page_token)
    resp = await loop.run_in_executor(None, lambda: client.task.v2.comment.list(builder.build()))
    if not resp.success():
        raise RuntimeError(f"comment.list failed: {resp.msg}, code={resp.code}")
    items = [_format_comment(c) for c in (resp.data.items or [])]
    return {
        "items": items,
        "has_more": getattr(resp.data, "has_more", False),
        "page_token": getattr(resp.data, "page_token", "") or "",
    }


async def get_task_comment(client: Any, comment_id: str) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.task.v2 import GetCommentRequest

    resp = await loop.run_in_executor(None, lambda: client.task.v2.comment.get(
        GetCommentRequest.builder().comment_id(comment_id).build()
    ))
    if not resp.success():
        raise RuntimeError(f"comment.get failed: {resp.msg}, code={resp.code}")
    return {"comment": _format_comment(resp.data.comment)}


async def update_task_comment(client: Any, comment_id: str, content: str) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.task.v2 import PatchCommentRequest, PatchCommentRequestBody
    from lark_oapi.api.task.v2.model import InputComment

    req = (
        PatchCommentRequest.builder()
        .comment_id(comment_id)
        .request_body(
            PatchCommentRequestBody.builder()
            .comment(InputComment.builder().content(content).build())
            .update_fields(["content"])
            .build()
        )
        .build()
    )
    resp = await loop.run_in_executor(None, lambda: client.task.v2.comment.patch(req))
    if not resp.success():
        raise RuntimeError(f"comment.patch failed: {resp.msg}, code={resp.code}")
    return {"comment": _format_comment(resp.data.comment)}


async def delete_task_comment(client: Any, comment_id: str) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.task.v2 import DeleteCommentRequest

    resp = await loop.run_in_executor(None, lambda: client.task.v2.comment.delete(
        DeleteCommentRequest.builder().comment_id(comment_id).build()
    ))
    if not resp.success():
        raise RuntimeError(f"comment.delete failed: {resp.msg}, code={resp.code}")
    return {"success": True, "comment_id": comment_id}


# ── Attachments ─────────────────────────────────────────────────────────────

async def upload_task_attachment(
    client: Any, task_guid: str,
    file_path: str | None = None, file_url: str | None = None,
    filename: str | None = None,
) -> dict[str, Any]:
    """Upload a file attachment to a task. Supports local file_path or remote file_url."""
    loop = asyncio.get_running_loop()
    tmp_path: str | None = None

    try:
        if file_url and not file_path:
            # Download from URL to a temp file
            import urllib.request
            suffix = os.path.splitext(file_url.split("?")[0])[-1] or ".bin"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp_path = tmp.name
            await loop.run_in_executor(None, lambda: urllib.request.urlretrieve(file_url, tmp_path))
            if not filename:
                filename = os.path.basename(file_url.split("?")[0]) or "attachment"
            file_path = tmp_path

        if not file_path:
            raise ValueError("Either file_path or file_url is required")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        fname = filename or os.path.basename(file_path)
        from lark_oapi.api.task.v2 import UploadAttachmentRequest, InputAttachment

        with open(file_path, "rb") as f:
            req = (
                UploadAttachmentRequest.builder()
                .request_body(
                    InputAttachment.builder()
                    .resource_type("task")
                    .resource_id(task_guid)
                    .file(f)
                    .build()
                )
                .build()
            )
            resp = await loop.run_in_executor(None, lambda: client.task.v2.attachment.upload(req))
        if not resp.success():
            raise RuntimeError(f"attachment.upload failed: {resp.msg}, code={resp.code}")
        items = [_format_attachment(a) for a in (getattr(resp.data, "items", None) or [])]
        return {"items": items}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


async def list_task_attachments(client: Any, task_guid: str, page_size: int = 50, page_token: str | None = None) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.task.v2 import ListAttachmentRequest

    builder = (
        ListAttachmentRequest.builder()
        .resource_type("task")
        .resource_id(task_guid)
        .page_size(min(page_size, 50))
    )
    if page_token:
        builder = builder.page_token(page_token)
    resp = await loop.run_in_executor(None, lambda: client.task.v2.attachment.list(builder.build()))
    if not resp.success():
        raise RuntimeError(f"attachment.list failed: {resp.msg}, code={resp.code}")
    items = [_format_attachment(a) for a in (resp.data.items or [])]
    return {
        "items": items,
        "has_more": getattr(resp.data, "has_more", False),
        "page_token": getattr(resp.data, "page_token", "") or "",
    }


async def get_task_attachment(client: Any, attachment_guid: str) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.task.v2 import GetAttachmentRequest

    resp = await loop.run_in_executor(None, lambda: client.task.v2.attachment.get(
        GetAttachmentRequest.builder().attachment_guid(attachment_guid).build()
    ))
    if not resp.success():
        raise RuntimeError(f"attachment.get failed: {resp.msg}, code={resp.code}")
    return {"attachment": _format_attachment(resp.data.attachment)}


async def delete_task_attachment(client: Any, attachment_guid: str) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.task.v2 import DeleteAttachmentRequest

    resp = await loop.run_in_executor(None, lambda: client.task.v2.attachment.delete(
        DeleteAttachmentRequest.builder().attachment_guid(attachment_guid).build()
    ))
    if not resp.success():
        raise RuntimeError(f"attachment.delete failed: {resp.msg}, code={resp.code}")
    return {"success": True, "attachment_guid": attachment_guid}
