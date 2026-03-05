"""Register feishu_wiki tool.

Mirrors: clawdbot-feishu/src/wiki-tools/register.ts
"""
from __future__ import annotations

import logging
from typing import Any

from ..tools_common.api import json_result, error_result
from .actions import list_spaces, list_nodes, get_node, create_node, move_node, rename_node

logger = logging.getLogger(__name__)

TOOL_NAME = "feishu_wiki"
TOOL_DESCRIPTION = (
    "Access and manage Feishu Wiki knowledge bases: list spaces, list/get nodes, "
    "create/move/rename nodes, and search. "
    "Key workflow: use 'get' to get obj_token, then feishu_doc to read/write the content."
)
TOOL_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["spaces", "nodes", "get", "search", "create", "move", "rename"],
            "description": (
                "'spaces': list all wiki spaces; "
                "'nodes': list nodes in a space; "
                "'get': get node metadata by wiki URL token (returns obj_token for feishu_doc); "
                "'search': search wiki content; "
                "'create': create a new wiki node; "
                "'move': move a node to a different space/parent; "
                "'rename': rename a node."
            ),
        },
        "space_id": {"type": "string", "description": "Wiki space ID (required for nodes/create/move/rename)."},
        "token": {"type": "string", "description": "Wiki node token from the URL (for 'get')."},
        "node_token": {"type": "string", "description": "Wiki node token (for move/rename)."},
        "parent_node_token": {"type": "string", "description": "Parent node token (for nodes/create)."},
        "title": {"type": "string", "description": "Node title (for create/rename)."},
        "obj_type": {
            "type": "string",
            "enum": ["docx", "sheet", "bitable"],
            "description": "Node type for create (default: docx).",
        },
        "target_space_id": {"type": "string", "description": "Target space id for move."},
        "target_parent_token": {"type": "string", "description": "Target parent node token for move."},
        "query": {"type": "string", "description": "Search query for 'search' action."},
        "page_token": {"type": "string", "description": "Pagination token."},
    },
    "required": ["action"],
}


async def run_feishu_wiki(params: dict[str, Any], client: Any) -> dict[str, Any]:
    action = params.get("action", "spaces")
    try:
        if action == "spaces":
            return json_result(await list_spaces(client))

        elif action == "nodes":
            space_id = params.get("space_id", "")
            if not space_id:
                return error_result("space_id is required for nodes")
            return json_result(await list_nodes(
                client, space_id,
                parent_node_token=params.get("parent_node_token"),
                page_token=params.get("page_token"),
            ))

        elif action == "get":
            token = params.get("token") or params.get("node_token", "")
            if not token:
                return error_result("token is required for get")
            return json_result(await get_node(client, token))

        elif action == "search":
            return error_result(
                "search is not implemented. Use 'nodes' to list and 'get' to look up nodes by token."
            )

        elif action == "create":
            space_id = params.get("space_id", "")
            title = params.get("title", "")
            if not space_id or not title:
                return error_result("space_id and title are required for create")
            return json_result(await create_node(
                client, space_id, title,
                obj_type=params.get("obj_type", "docx"),
                parent_node_token=params.get("parent_node_token"),
            ))

        elif action == "move":
            space_id = params.get("space_id", "")
            node_token = params.get("node_token", "")
            if not space_id or not node_token:
                return error_result("space_id and node_token are required for move")
            return json_result(await move_node(
                client, space_id, node_token,
                target_space_id=params.get("target_space_id"),
                target_parent_token=params.get("target_parent_token"),
            ))

        elif action == "rename":
            space_id = params.get("space_id", "")
            node_token = params.get("node_token", "")
            title = params.get("title", "")
            if not space_id or not node_token or not title:
                return error_result("space_id, node_token, and title are required for rename")
            return json_result(await rename_node(client, space_id, node_token, title))

        return error_result(f"Unknown action: {action}")
    except Exception as e:
        logger.warning("feishu_wiki[%s] error: %s", action, e)
        return error_result(e)


def register_wiki_tools(api: Any) -> None:
    api.register_tool(name=TOOL_NAME, description=TOOL_DESCRIPTION, schema=TOOL_SCHEMA, handler=run_feishu_wiki)
    logger.info("Registered wiki tools: %s", TOOL_NAME)
