"""Register feishu_drive tool.

Mirrors: clawdbot-feishu/src/drive-tools/register.ts
"""
from __future__ import annotations

import logging
from typing import Any

from ..tools_common.api import json_result, error_result
from .actions import list_folder, get_file_info, create_folder, move_file, delete_file, import_document

logger = logging.getLogger(__name__)

TOOL_NAME = "feishu_drive"
TOOL_DESCRIPTION = (
    "Manage Feishu Drive (cloud storage): list folders, get file info, create folders, "
    "move/delete files, and import Markdown as a new document. "
    "Note: bots have no 'My Space' root — share a folder with the bot before creating files in it."
)
TOOL_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["list", "info", "create_folder", "move", "delete", "import_document"],
            "description": (
                "'list': list files in a folder; "
                "'info': get file metadata by token; "
                "'create_folder': create a new folder; "
                "'move': move a file to another folder; "
                "'delete': delete a file or folder; "
                "'import_document': create a new Feishu doc from markdown."
            ),
        },
        "folder_token": {"type": "string", "description": "Folder token (empty = root for list)."},
        "file_token": {"type": "string", "description": "File/folder token (required for info/move/delete)."},
        "type": {
            "type": "string",
            "enum": ["doc", "docx", "sheet", "bitable", "folder", "file", "mindnote", "shortcut"],
            "description": "File type — required for info/move/delete.",
        },
        "name": {"type": "string", "description": "Folder name for create_folder."},
        "title": {"type": "string", "description": "Document title for import_document."},
        "content": {"type": "string", "description": "Markdown content for import_document."},
        "page_token": {"type": "string", "description": "Pagination token for list."},
        "file_type": {"type": "string", "description": "Filter file type for list."},
    },
    "required": ["action"],
}


async def run_feishu_drive(params: dict[str, Any], client: Any) -> dict[str, Any]:
    action = params.get("action", "list")
    try:
        if action == "list":
            return json_result(await list_folder(
                client,
                folder_token=params.get("folder_token"),
                page_token=params.get("page_token"),
                file_type=params.get("file_type"),
            ))

        elif action == "info":
            file_token = params.get("file_token", "")
            file_type = params.get("type", "file")
            if not file_token:
                return error_result("file_token is required for info")
            return json_result(await get_file_info(client, file_token, file_type))

        elif action == "create_folder":
            name = params.get("name", "")
            if not name:
                return error_result("name is required for create_folder")
            return json_result(await create_folder(client, name, folder_token=params.get("folder_token")))

        elif action == "move":
            file_token = params.get("file_token", "")
            file_type = params.get("type", "file")
            folder_token = params.get("folder_token", "")
            if not file_token or not folder_token:
                return error_result("file_token and folder_token are required for move")
            return json_result(await move_file(client, file_token, file_type, folder_token))

        elif action == "delete":
            file_token = params.get("file_token", "")
            file_type = params.get("type", "file")
            if not file_token:
                return error_result("file_token is required for delete")
            return json_result(await delete_file(client, file_token, file_type))

        elif action == "import_document":
            title = params.get("title", "Untitled")
            content = params.get("content", "")
            if not content:
                return error_result("content is required for import_document")
            return json_result(await import_document(client, title, content, folder_token=params.get("folder_token")))

        return error_result(f"Unknown action: {action}")
    except Exception as e:
        logger.warning("feishu_drive[%s] error: %s", action, e)
        return error_result(e)


def register_drive_tools(api: Any) -> None:
    api.register_tool(name=TOOL_NAME, description=TOOL_DESCRIPTION, schema=TOOL_SCHEMA, handler=run_feishu_drive)
    logger.info("Registered drive tools: %s", TOOL_NAME)
