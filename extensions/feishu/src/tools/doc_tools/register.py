"""Register feishu_doc and feishu_app_scopes tools with the plugin API.

Mirrors: clawdbot-feishu/src/doc-tools/register.ts
"""
from __future__ import annotations

import logging
from typing import Any

from .schemas import (
    DOC_TOOL_NAME, DOC_TOOL_DESCRIPTION, DOC_TOOL_SCHEMA,
    SCOPES_TOOL_NAME, SCOPES_TOOL_DESCRIPTION, SCOPES_TOOL_SCHEMA,
)
from .actions import (
    read_doc, list_blocks, get_block, update_block, delete_block,
    list_comments, create_comment, get_comment, list_comment_replies,
    list_app_scopes,
)
from ..tools_common.api import json_result, error_result

logger = logging.getLogger(__name__)


async def run_feishu_doc(params: dict[str, Any], client: Any) -> dict[str, Any]:
    """Dispatch feishu_doc tool call to the correct action handler."""
    action = params.get("action", "read")
    doc_token = params.get("doc_token") or params.get("document_id", "")

    try:
        if action == "read":
            if not doc_token:
                return error_result("doc_token is required for read")
            return json_result(await read_doc(client, doc_token))

        elif action == "write":
            if not doc_token:
                return error_result("doc_token is required for write")
            content = params.get("content", "")
            if not content:
                return error_result("content is required for write")
            from ...doc_write_service import write_doc
            result = await write_doc(client, doc_token, content)
            return json_result({"success": result.success, "blocks_deleted": result.blocks_deleted, "blocks_added": result.blocks_added, "warning": result.warning})

        elif action == "append":
            if not doc_token:
                return error_result("doc_token is required for append")
            content = params.get("content", "")
            if not content:
                return error_result("content is required for append")
            from ...doc_write_service import append_doc
            result = await append_doc(client, doc_token, content)
            return json_result({"success": result.success, "blocks_added": result.blocks_added, "block_ids": result.block_ids, "warning": result.warning})

        elif action == "create":
            title = params.get("title", "Untitled")
            folder_token = params.get("folder_token") or None
            from ...doc_write_service import create_doc
            result = await create_doc(client, title, folder_token)
            return json_result({"document_id": result.document_id, "title": result.title, "url": result.url})

        elif action == "create_and_write":
            title = params.get("title", "Untitled")
            content = params.get("content", "")
            if not content:
                return error_result("content is required for create_and_write")
            folder_token = params.get("folder_token") or None
            from ...doc_write_service import create_and_write_doc
            result = await create_and_write_doc(client, title, content, folder_token)
            return json_result({"document_id": result.document_id, "title": result.title, "url": result.url, "blocks_added": result.blocks_added, "warning": result.warning})

        elif action == "list_blocks":
            if not doc_token:
                return error_result("doc_token is required for list_blocks")
            return json_result(await list_blocks(client, doc_token))

        elif action == "get_block":
            if not doc_token:
                return error_result("doc_token is required for get_block")
            block_id = params.get("block_id", "")
            if not block_id:
                return error_result("block_id is required for get_block")
            return json_result(await get_block(client, doc_token, block_id))

        elif action == "update_block":
            if not doc_token:
                return error_result("doc_token is required for update_block")
            block_id = params.get("block_id", "")
            content = params.get("content", "")
            if not block_id or not content:
                return error_result("block_id and content are required for update_block")
            return json_result(await update_block(client, doc_token, block_id, content))

        elif action == "delete_block":
            if not doc_token:
                return error_result("doc_token is required for delete_block")
            block_id = params.get("block_id", "")
            if not block_id:
                return error_result("block_id is required for delete_block")
            return json_result(await delete_block(client, doc_token, block_id))

        elif action == "list_comments":
            if not doc_token:
                return error_result("doc_token is required for list_comments")
            return json_result(await list_comments(
                client, doc_token,
                page_token=params.get("page_token"),
                page_size=int(params.get("page_size", 50)),
            ))

        elif action == "create_comment":
            if not doc_token:
                return error_result("doc_token is required for create_comment")
            content = params.get("content", "")
            if not content:
                return error_result("content is required for create_comment")
            return json_result(await create_comment(client, doc_token, content))

        elif action == "get_comment":
            if not doc_token:
                return error_result("doc_token is required for get_comment")
            comment_id = params.get("comment_id", "")
            if not comment_id:
                return error_result("comment_id is required for get_comment")
            return json_result(await get_comment(client, doc_token, comment_id))

        elif action == "list_comment_replies":
            if not doc_token:
                return error_result("doc_token is required for list_comment_replies")
            comment_id = params.get("comment_id", "")
            if not comment_id:
                return error_result("comment_id is required for list_comment_replies")
            return json_result(await list_comment_replies(
                client, doc_token, comment_id,
                page_token=params.get("page_token"),
                page_size=int(params.get("page_size", 50)),
            ))

        return error_result(f"Unknown action: {action}")

    except Exception as e:
        logger.warning("feishu_doc[%s] error: %s", action, e)
        return error_result(e)


async def run_feishu_app_scopes(params: dict[str, Any], client: Any) -> dict[str, Any]:
    try:
        return json_result(await list_app_scopes(client))
    except Exception as e:
        return error_result(e)


def register_doc_tools(api: Any) -> None:
    """Register feishu_doc and feishu_app_scopes with the plugin API."""
    api.register_tool(
        name=DOC_TOOL_NAME,
        description=DOC_TOOL_DESCRIPTION,
        schema=DOC_TOOL_SCHEMA,
        handler=run_feishu_doc,
    )
    api.register_tool(
        name=SCOPES_TOOL_NAME,
        description=SCOPES_TOOL_DESCRIPTION,
        schema=SCOPES_TOOL_SCHEMA,
        handler=run_feishu_app_scopes,
    )
    logger.info("Registered doc tools: %s, %s", DOC_TOOL_NAME, SCOPES_TOOL_NAME)
