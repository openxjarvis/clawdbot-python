"""Drive action implementations.

Mirrors: clawdbot-feishu/src/drive-tools/actions.ts
"""
from __future__ import annotations

import asyncio
from typing import Any

_FILE_FIELDS = ["token", "name", "type", "url", "parent_token", "created_time", "modified_time", "owner_id"]


def _format_file(f: Any) -> dict[str, Any]:
    return {k: getattr(f, k, "") for k in _FILE_FIELDS}


async def list_folder(client: Any, folder_token: str | None = None, page_token: str | None = None, file_type: str | None = None) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.drive.v1 import ListFileRequest

    builder = ListFileRequest.builder()
    if folder_token:
        builder = builder.folder_token(folder_token)
    if page_token:
        builder = builder.page_token(page_token)
    if file_type:
        builder = builder.type(file_type)
    resp = await loop.run_in_executor(None, lambda: client.drive.v1.file.list(builder.build()))
    if not resp.success():
        raise RuntimeError(f"drive.file.list failed: {resp.msg}, code={resp.code}")
    files = [_format_file(f) for f in (resp.data.files or [])]
    return {
        "files": files,
        "has_more": getattr(resp.data, "has_more", False),
        "next_page_token": getattr(resp.data, "next_page_token", "") or "",
    }


async def get_file_info(client: Any, file_token: str, file_type: str) -> dict[str, Any]:
    """Get metadata for a specific file by listing and finding it, or using get_meta API."""
    loop = asyncio.get_running_loop()
    try:
        from lark_oapi.api.drive.v1 import GetFileMetaRequest
        req = GetFileMetaRequest.builder().file_token(file_token).build()
        resp = await loop.run_in_executor(None, lambda: client.drive.v1.file.get_meta(req))
        if resp.success() and resp.data and resp.data.meta:
            return _format_file(resp.data.meta)
    except Exception:
        pass
    # Fallback: list files and find by token
    result = await list_folder(client)
    for f in result.get("files", []):
        if f.get("token") == file_token:
            return f
    raise RuntimeError(f"File {file_token} not found")


async def create_folder(client: Any, name: str, folder_token: str | None = None) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.drive.v1 import CreateFolderFileRequest, CreateFolderFileRequestBody

    # Try to resolve root folder token if none provided
    resolved_token = folder_token
    if not resolved_token:
        try:
            import lark_oapi as lark
            req = lark.RawRequestOpts(
                method="GET",
                url="/open-apis/drive/explorer/v2/root_folder/meta",
                access_token_type=lark.AccessTokenType.TENANT,
            )
            meta_resp = await loop.run_in_executor(None, lambda: client.request(req))
            if getattr(meta_resp, "success", lambda: False)():
                resolved_token = getattr(meta_resp.data, "token", None)
        except Exception:
            resolved_token = "0"

    body = CreateFolderFileRequestBody.builder().name(name).folder_token(resolved_token or "0").build()
    req = CreateFolderFileRequest.builder().request_body(body).build()
    resp = await loop.run_in_executor(None, lambda: client.drive.v1.file.create_folder(req))
    if not resp.success():
        raise RuntimeError(f"drive.file.create_folder failed: {resp.msg}, code={resp.code}")
    return {
        "token": getattr(resp.data, "token", ""),
        "url": getattr(resp.data, "url", ""),
    }


async def move_file(client: Any, file_token: str, file_type: str, folder_token: str) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.drive.v1 import MoveFileRequest, MoveFileRequestBody

    req = (
        MoveFileRequest.builder()
        .file_token(file_token)
        .request_body(MoveFileRequestBody.builder().type(file_type).folder_token(folder_token).build())
        .build()
    )
    resp = await loop.run_in_executor(None, lambda: client.drive.v1.file.move(req))
    if not resp.success():
        raise RuntimeError(f"drive.file.move failed: {resp.msg}, code={resp.code}")
    return {"success": True, "task_id": getattr(resp.data, "task_id", "")}


async def delete_file(client: Any, file_token: str, file_type: str) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.drive.v1 import DeleteFileRequest

    req = DeleteFileRequest.builder().file_token(file_token).type(file_type).build()
    resp = await loop.run_in_executor(None, lambda: client.drive.v1.file.delete(req))
    if not resp.success():
        raise RuntimeError(f"drive.file.delete failed: {resp.msg}, code={resp.code}")
    return {"success": True, "task_id": getattr(resp.data, "task_id", "")}


async def import_document(
    client: Any, title: str, content: str, folder_token: str | None = None
) -> dict[str, Any]:
    """Import Markdown as a new Feishu document. Delegates to doc_write_service."""
    from ...doc_write_service import create_and_write_doc
    result = await create_and_write_doc(client, title, content, folder_token)
    return {
        "document_id": result.document_id,
        "title": result.title,
        "url": result.url,
        "blocks_added": result.blocks_added,
        "warning": result.warning,
    }
