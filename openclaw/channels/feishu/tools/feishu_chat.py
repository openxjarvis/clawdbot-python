"""feishu_chat tool — chat info and member listing.

Mirrors TypeScript: extensions/feishu/src/chat.ts
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

TOOL_NAME = "feishu_chat"
TOOL_DESCRIPTION = (
    "Get information about a Feishu group chat or list its members. "
    "Use chat_id starting with 'oc_' for groups."
)
TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "chat_id": {
            "type": "string",
            "description": "The Feishu chat ID (e.g. oc_xxxxxxxx) to get info for.",
        },
        "action": {
            "type": "string",
            "enum": ["info", "members", "search", "create", "update"],
            "description": (
                "Action: 'info' returns chat metadata, 'members' lists members, "
                "'search' finds chats by keyword, 'create' creates a new group chat, "
                "'update' updates chat settings."
            ),
        },
        "query": {
            "type": "string",
            "description": "Search keyword for 'search' action.",
        },
        "name": {
            "type": "string",
            "description": "Group chat name for 'create' or 'update' action.",
        },
        "description": {
            "type": "string",
            "description": "Group chat description for 'create' or 'update' action.",
        },
        "user_id_list": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of user open_ids to add when creating a chat.",
        },
        "page_token": {
            "type": "string",
            "description": "Pagination token for members/search listing.",
        },
    },
    "required": ["action"],
}


async def run_feishu_chat(
    params: dict[str, Any],
    client: Any,
) -> dict[str, Any]:
    """Execute feishu_chat tool call."""
    chat_id = params.get("chat_id", "")
    action = params.get("action", "info")
    page_token = params.get("page_token", "")

    loop = asyncio.get_running_loop()

    if action == "info":
        from lark_oapi.api.im.v1 import GetChatRequest

        try:
            request = GetChatRequest.builder().chat_id(chat_id).build()
            response = await loop.run_in_executor(None, lambda: client.im.v1.chat.get(request))
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            chat = response.data
            return {
                "chat_id": chat_id,
                "name": getattr(chat, "name", ""),
                "description": getattr(chat, "description", ""),
                "owner_id": getattr(chat, "owner_id", ""),
                "member_count": getattr(chat, "member_count", 0),
                "chat_type": getattr(chat, "chat_type", ""),
            }
        except Exception as e:
            return {"error": str(e)}

    elif action == "members":
        from lark_oapi.api.im.v1 import GetChatMembersRequest

        try:
            builder = GetChatMembersRequest.builder().chat_id(chat_id)
            if page_token:
                builder = builder.page_token(page_token)
            request = builder.build()
            response = await loop.run_in_executor(None, lambda: client.im.v1.chat_members.get(request))
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            data = response.data
            members = []
            for m in (data.items or []):
                members.append({
                    "member_id": getattr(m, "member_id", ""),
                    "name": getattr(m, "name", ""),
                    "tenant_key": getattr(m, "tenant_key", ""),
                    "member_id_type": getattr(m, "member_id_type", ""),
                })
            return {
                "chat_id": chat_id,
                "members": members,
                "has_more": getattr(data, "has_more", False),
                "page_token": getattr(data, "page_token", ""),
                "member_total": getattr(data, "member_total", len(members)),
            }
        except Exception as e:
            return {"error": str(e)}

    elif action == "search":
        query = params.get("query", "")
        page_token = params.get("page_token", "")
        try:
            from lark_oapi.api.im.v1 import SearchChatRequest

            builder = SearchChatRequest.builder()
            if query:
                builder = builder.query(query)
            if page_token:
                builder = builder.page_token(page_token)
            request = builder.build()
            response = await loop.run_in_executor(None, lambda: client.im.v1.chat.search(request))
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            items = []
            for c in (getattr(response.data, "items", None) or []):
                items.append({
                    "chat_id": getattr(c, "chat_id", ""),
                    "name": getattr(c, "name", ""),
                    "description": getattr(c, "description", ""),
                    "owner_id": getattr(c, "owner_id", ""),
                })
            return {
                "items": items,
                "has_more": getattr(response.data, "has_more", False),
                "page_token": getattr(response.data, "page_token", ""),
            }
        except Exception as e:
            return {"error": str(e)}

    elif action == "create":
        name = params.get("name", "New Group")
        description = params.get("description", "")
        user_ids = params.get("user_id_list") or []
        try:
            from lark_oapi.api.im.v1 import CreateChatRequest, CreateChatRequestBody

            builder = CreateChatRequestBody.builder().name(name)
            if description:
                builder = builder.description(description)
            if user_ids:
                builder = builder.user_id_list(user_ids)
            request = (
                CreateChatRequest.builder()
                .request_body(builder.build())
                .build()
            )
            response = await loop.run_in_executor(None, lambda: client.im.v1.chat.create(request))
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            return {
                "chat_id": getattr(response.data, "chat_id", ""),
                "name": name,
            }
        except Exception as e:
            return {"error": str(e)}

    elif action == "update":
        if not chat_id:
            return {"error": "chat_id is required for update"}
        name = params.get("name")
        description = params.get("description")
        try:
            from lark_oapi.api.im.v1 import UpdateChatRequest, UpdateChatRequestBody

            builder = UpdateChatRequestBody.builder()
            if name is not None:
                builder = builder.name(name)
            if description is not None:
                builder = builder.description(description)
            request = (
                UpdateChatRequest.builder()
                .chat_id(chat_id)
                .request_body(builder.build())
                .build()
            )
            response = await loop.run_in_executor(None, lambda: client.im.v1.chat.update(request))
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            return {"chat_id": chat_id, "status": "updated"}
        except Exception as e:
            return {"error": str(e)}

    return {"error": f"Unknown action: {action}"}
