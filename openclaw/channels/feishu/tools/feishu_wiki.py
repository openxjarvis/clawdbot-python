"""feishu_wiki tool — Feishu knowledge base (Wiki) operations.

Mirrors TypeScript: extensions/feishu/src/wiki.ts
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

TOOL_NAME = "feishu_wiki"
TOOL_DESCRIPTION = (
    "Access Feishu knowledge base (Wiki): list spaces, get nodes, search content."
)
TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["list_spaces", "list_nodes", "get_node", "search"],
            "description": "Action to perform on the Feishu Wiki.",
        },
        "space_id": {
            "type": "string",
            "description": "Wiki space ID (required for list_nodes).",
        },
        "node_token": {
            "type": "string",
            "description": "Wiki node token (required for get_node).",
        },
        "query": {
            "type": "string",
            "description": "Search query (for search action).",
        },
        "page_token": {
            "type": "string",
            "description": "Pagination token.",
        },
    },
    "required": ["action"],
}


async def run_feishu_wiki(
    params: dict[str, Any],
    client: Any,
) -> dict[str, Any]:
    """Execute feishu_wiki tool call."""
    action = params.get("action", "list_spaces")
    loop = asyncio.get_running_loop()

    if action == "list_spaces":
        try:
            from lark_oapi.api.wiki.v2 import ListSpaceRequest

            request = ListSpaceRequest.builder().build()
            response = await loop.run_in_executor(
                None, lambda: client.wiki.v2.space.list(request)
            )
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            spaces = []
            for s in (response.data.items or []):
                spaces.append({
                    "space_id": getattr(s, "space_id", ""),
                    "name": getattr(s, "name", ""),
                    "description": getattr(s, "description", ""),
                })
            return {"spaces": spaces}
        except Exception as e:
            return {"error": str(e)}

    elif action == "list_nodes":
        space_id = params.get("space_id", "")
        if not space_id:
            return {"error": "space_id is required for list_nodes"}
        page_token = params.get("page_token", "")
        try:
            from lark_oapi.api.wiki.v2 import ListSpaceNodeRequest

            builder = ListSpaceNodeRequest.builder().space_id(space_id)
            if page_token:
                builder = builder.page_token(page_token)
            request = builder.build()
            response = await loop.run_in_executor(
                None, lambda: client.wiki.v2.space_node.list(request)
            )
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            nodes = []
            for n in (response.data.items or []):
                nodes.append({
                    "node_token": getattr(n, "node_token", ""),
                    "title": getattr(n, "title", ""),
                    "node_type": getattr(n, "node_type", ""),
                    "obj_type": getattr(n, "obj_type", ""),
                    "obj_token": getattr(n, "obj_token", ""),
                    "has_child": getattr(n, "has_child", False),
                })
            return {
                "nodes": nodes,
                "has_more": getattr(response.data, "has_more", False),
                "page_token": getattr(response.data, "page_token", ""),
            }
        except Exception as e:
            return {"error": str(e)}

    elif action == "get_node":
        node_token = params.get("node_token", "")
        space_id = params.get("space_id", "")
        if not node_token:
            return {"error": "node_token is required"}
        try:
            from lark_oapi.api.wiki.v2 import GetSpaceNodeRequest

            request = (
                GetSpaceNodeRequest.builder()
                .token(node_token)
                .build()
            )
            response = await loop.run_in_executor(
                None, lambda: client.wiki.v2.space_node.get(request)
            )
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            node = response.data.node
            return {
                "node_token": getattr(node, "node_token", ""),
                "title": getattr(node, "title", ""),
                "obj_type": getattr(node, "obj_type", ""),
                "obj_token": getattr(node, "obj_token", ""),
                "url": getattr(node, "url", ""),
            }
        except Exception as e:
            return {"error": str(e)}

    elif action == "search":
        query = params.get("query", "")
        if not query:
            return {"error": "query is required for search"}
        try:
            from lark_oapi.api.wiki.v2 import SearchWikiRequest, SearchWikiRequestBody

            request = (
                SearchWikiRequest.builder()
                .request_body(
                    SearchWikiRequestBody.builder()
                    .query(query)
                    .build()
                )
                .build()
            )
            response = await loop.run_in_executor(
                None, lambda: client.wiki.v2.space.search_wiki(request)
            )
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            items = []
            for item in (response.data.items or []):
                items.append({
                    "node_token": getattr(item, "node_token", ""),
                    "title": getattr(item, "title", ""),
                    "url": getattr(item, "url", ""),
                })
            return {"results": items}
        except Exception as e:
            return {"error": str(e)}

    return {"error": f"Unknown action: {action}"}
