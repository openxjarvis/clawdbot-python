"""feishu_drive tool — Feishu cloud storage (Drive) operations.

Mirrors TypeScript: extensions/feishu/src/drive.ts
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

TOOL_NAME = "feishu_drive"
TOOL_DESCRIPTION = (
    "Access Feishu cloud storage (Drive): list files, get file info, move files."
)
TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["list", "get", "move", "copy", "delete"],
            "description": "Action to perform.",
        },
        "folder_token": {
            "type": "string",
            "description": "Folder token to list (empty = root).",
        },
        "file_token": {
            "type": "string",
            "description": "File token for get/move/copy/delete.",
        },
        "file_type": {
            "type": "string",
            "description": "File type filter: 'doc', 'sheet', 'bitable', 'file', etc.",
        },
        "target_folder_token": {
            "type": "string",
            "description": "Destination folder token for move/copy.",
        },
        "new_title": {
            "type": "string",
            "description": "New title for copy.",
        },
        "page_token": {
            "type": "string",
            "description": "Pagination token.",
        },
    },
    "required": ["action"],
}


async def run_feishu_drive(
    params: dict[str, Any],
    client: Any,
) -> dict[str, Any]:
    """Execute feishu_drive tool call."""
    action = params.get("action", "list")
    loop = asyncio.get_running_loop()

    if action == "list":
        folder_token = params.get("folder_token", "")
        page_token = params.get("page_token", "")
        file_type = params.get("file_type", "")
        try:
            from lark_oapi.api.drive.v1 import ListFileRequest

            builder = ListFileRequest.builder()
            if folder_token:
                builder = builder.folder_token(folder_token)
            if page_token:
                builder = builder.page_token(page_token)
            if file_type:
                builder = builder.type(file_type)
            request = builder.build()
            response = await loop.run_in_executor(
                None, lambda: client.drive.v1.file.list(request)
            )
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            files = []
            for f in (response.data.files or []):
                files.append({
                    "token": getattr(f, "token", ""),
                    "name": getattr(f, "name", ""),
                    "type": getattr(f, "type", ""),
                    "parent_token": getattr(f, "parent_token", ""),
                    "url": getattr(f, "url", ""),
                    "modified_time": getattr(f, "modified_time", ""),
                })
            return {
                "files": files,
                "has_more": getattr(response.data, "has_more", False),
                "next_page_token": getattr(response.data, "next_page_token", ""),
            }
        except Exception as e:
            return {"error": str(e)}

    elif action == "get":
        file_token = params.get("file_token", "")
        if not file_token:
            return {"error": "file_token is required"}
        try:
            from lark_oapi.api.drive.v1 import GetFileMeta, GetFileMetaRequest

            request = GetFileMetaRequest.builder().file_token(file_token).build()
            response = await loop.run_in_executor(
                None, lambda: client.drive.v1.file.get_meta(request)
            )
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            meta = response.data.meta
            return {
                "token": getattr(meta, "token", ""),
                "name": getattr(meta, "name", ""),
                "type": getattr(meta, "type", ""),
                "url": getattr(meta, "url", ""),
                "owner_id": getattr(meta, "owner_id", ""),
            }
        except Exception as e:
            return {"error": str(e)}

    elif action == "copy":
        file_token = params.get("file_token", "")
        target_folder = params.get("target_folder_token", "")
        new_title = params.get("new_title", "")
        if not file_token or not target_folder:
            return {"error": "file_token and target_folder_token are required"}
        try:
            from lark_oapi.api.drive.v1 import CopyFileRequest, CopyFileRequestBody

            builder = CopyFileRequestBody.builder().folder_token(target_folder)
            if new_title:
                builder = builder.name(new_title)
            request = (
                CopyFileRequest.builder()
                .file_token(file_token)
                .request_body(builder.build())
                .build()
            )
            response = await loop.run_in_executor(
                None, lambda: client.drive.v1.file.copy(request)
            )
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            return {
                "token": getattr(response.data, "token", ""),
                "url": getattr(response.data, "url", ""),
            }
        except Exception as e:
            return {"error": str(e)}

    elif action == "move":
        file_token = params.get("file_token", "")
        target_folder = params.get("target_folder_token", "")
        file_type = params.get("file_type", "file")
        if not file_token or not target_folder:
            return {"error": "file_token and target_folder_token are required"}
        try:
            from lark_oapi.api.drive.v1 import MoveFileRequest, MoveFileRequestBody

            request = (
                MoveFileRequest.builder()
                .file_token(file_token)
                .request_body(
                    MoveFileRequestBody.builder()
                    .type(file_type)
                    .folder_token(target_folder)
                    .build()
                )
                .build()
            )
            response = await loop.run_in_executor(
                None, lambda: client.drive.v1.file.move(request)
            )
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            task = getattr(response.data, "task_id", "")
            return {"status": "moved", "token": file_token, "task_id": task}
        except Exception as e:
            return {"error": str(e)}

    elif action == "delete":
        file_token = params.get("file_token", "")
        file_type = params.get("file_type", "file")
        if not file_token:
            return {"error": "file_token is required"}
        try:
            from lark_oapi.api.drive.v1 import DeleteFileRequest

            request = (
                DeleteFileRequest.builder()
                .file_token(file_token)
                .type(file_type)
                .build()
            )
            response = await loop.run_in_executor(
                None, lambda: client.drive.v1.file.delete(request)
            )
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            return {"status": "deleted", "token": file_token}
        except Exception as e:
            return {"error": str(e)}

    return {"error": f"Unknown action: {action}"}
