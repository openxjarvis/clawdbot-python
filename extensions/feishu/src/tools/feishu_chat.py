"""feishu_chat tool — group chat management.

Mirrors TypeScript: clawdbot-feishu/src/channel.ts (chat operations)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

TOOL_NAME = "feishu_chat"
TOOL_DESCRIPTION = (
    "Manage Feishu group chats: get info, list/add members, search, create, update, delete, "
    "read/write group announcements, and check bot membership. "
    "Use chat_id starting with 'oc_' for groups. "
    "Note: 'delete' requires the bot to be the group owner."
)
TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "chat_id": {
            "type": "string",
            "description": "The Feishu chat ID (e.g. oc_xxxxxxxx).",
        },
        "action": {
            "type": "string",
            "enum": [
                "info", "members", "search", "create", "update",
                "delete", "add_members", "get_announcement",
                "update_announcement", "check_membership",
            ],
            "description": (
                "'info': chat metadata; 'members': list members; "
                "'search': find chats by keyword; 'create': new group; "
                "'update': update settings; 'delete': disband (bot must be owner); "
                "'add_members': add user(s) to chat; "
                "'get_announcement': read group announcement; "
                "'update_announcement': write group announcement (markdown); "
                "'check_membership': check if bot is in the chat."
            ),
        },
        "query": {
            "type": "string",
            "description": "Search keyword for 'search' action.",
        },
        "name": {
            "type": "string",
            "description": "Group chat name for 'create' or 'update'.",
        },
        "description": {
            "type": "string",
            "description": "Group chat description for 'create' or 'update'.",
        },
        "user_id_list": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of user open_ids to add (create or add_members).",
        },
        "content": {
            "type": "string",
            "description": "Announcement content (markdown) for 'update_announcement'.",
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

    elif action == "delete":
        if not chat_id:
            return {"error": "chat_id is required for delete"}
        try:
            from lark_oapi.api.im.v1 import DeleteChatRequest

            request = DeleteChatRequest.builder().chat_id(chat_id).build()
            response = await loop.run_in_executor(None, lambda: client.im.v1.chat.delete(request))
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            return {"chat_id": chat_id, "status": "deleted"}
        except Exception as e:
            return {"error": str(e)}

    elif action == "add_members":
        if not chat_id:
            return {"error": "chat_id is required for add_members"}
        user_ids = params.get("user_id_list") or []
        if not user_ids:
            return {"error": "user_id_list is required for add_members"}
        try:
            from lark_oapi.api.im.v1 import CreateChatMembersRequest, CreateChatMembersRequestBody

            request = (
                CreateChatMembersRequest.builder()
                .chat_id(chat_id)
                .member_id_type("open_id")
                .request_body(
                    CreateChatMembersRequestBody.builder()
                    .id_list(user_ids)
                    .build()
                )
                .build()
            )
            response = await loop.run_in_executor(None, lambda: client.im.v1.chat_members.create(request))
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            return {
                "chat_id": chat_id,
                "status": "members_added",
                "invalid_id_list": getattr(response.data, "invalid_id_list", []) or [],
            }
        except Exception as e:
            return {"error": str(e)}

    elif action == "get_announcement":
        if not chat_id:
            return {"error": "chat_id is required for get_announcement"}
        try:
            from lark_oapi.api.im.v1 import GetChatAnnouncementRequest

            request = GetChatAnnouncementRequest.builder().chat_id(chat_id).build()
            response = await loop.run_in_executor(None, lambda: client.im.v1.chat_announcement.get(request))
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            data = response.data
            return {
                "chat_id": chat_id,
                "content": getattr(data, "content", ""),
                "revision_id": getattr(data, "revision_id", ""),
                "update_time": getattr(data, "update_time", ""),
            }
        except Exception as e:
            return {"error": str(e)}

    elif action == "update_announcement":
        if not chat_id:
            return {"error": "chat_id is required for update_announcement"}
        content = params.get("content", "")
        if not content:
            return {"error": "content is required for update_announcement"}
        try:
            from lark_oapi.api.im.v1 import PatchChatAnnouncementRequest, PatchChatAnnouncementRequestBody

            request = (
                PatchChatAnnouncementRequest.builder()
                .chat_id(chat_id)
                .request_body(
                    PatchChatAnnouncementRequestBody.builder()
                    .revision_id("0")
                    .requests([{"type": "replace_all", "content": content}])
                    .build()
                )
                .build()
            )
            response = await loop.run_in_executor(None, lambda: client.im.v1.chat_announcement.patch(request))
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            return {"chat_id": chat_id, "status": "announcement_updated"}
        except Exception as e:
            return {"error": str(e)}

    elif action == "check_membership":
        if not chat_id:
            return {"error": "chat_id is required for check_membership"}
        try:
            from lark_oapi.api.im.v1 import IsInChatChatMembersRequest

            request = IsInChatChatMembersRequest.builder().chat_id(chat_id).build()
            response = await loop.run_in_executor(None, lambda: client.im.v1.chat_members.is_in_chat(request))
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            return {
                "chat_id": chat_id,
                "is_in_chat": getattr(response.data, "is_in_chat", False),
            }
        except Exception as e:
            return {"error": str(e)}

    return {"error": f"Unknown action: {action}"}
