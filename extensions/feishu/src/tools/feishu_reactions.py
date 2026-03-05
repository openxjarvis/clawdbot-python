"""feishu_reactions tool — standalone emoji reactions on Feishu messages.

Mirrors TypeScript: addReactionFeishu / removeReactionFeishu / listReactionsFeishu
in extensions/feishu/src/reactions.ts.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

TOOL_NAME = "feishu_reactions"
TOOL_DESCRIPTION = (
    "Add, remove, or list emoji reactions on a Feishu message. "
    "Mirrors the Feishu im.message.reaction API."
)
TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["add", "remove", "list"],
            "description": "Action: 'add' adds a reaction, 'remove' removes one, 'list' lists all reactions.",
        },
        "message_id": {
            "type": "string",
            "description": "Feishu message ID (om_xxxxxxxx).",
        },
        "emoji": {
            "type": "string",
            "description": "Emoji type key for add/remove (e.g. 'THUMBSUP', 'OK', 'CLAP'). "
                           "See Feishu reaction emoji list for valid keys.",
        },
        "page_token": {
            "type": "string",
            "description": "Pagination token for list action.",
        },
    },
    "required": ["action", "message_id"],
}


async def run_feishu_reactions(
    params: dict[str, Any],
    client: Any,
) -> dict[str, Any]:
    """Execute feishu_reactions tool call."""
    action = params.get("action", "list")
    message_id = params.get("message_id", "")
    emoji = params.get("emoji", "")
    page_token = params.get("page_token", "")
    loop = asyncio.get_running_loop()

    if not message_id:
        return {"error": "message_id is required"}

    if action == "add":
        if not emoji:
            return {"error": "emoji is required for add action"}
        try:
            from lark_oapi.api.im.v1 import (
                CreateMessageReactionRequest, CreateMessageReactionRequestBody,
            )
            from lark_oapi.api.im.v1.model import EmojiType

            request = (
                CreateMessageReactionRequest.builder()
                .message_id(message_id)
                .request_body(
                    CreateMessageReactionRequestBody.builder()
                    .reaction_type(
                        EmojiType.builder().emoji_type(emoji).build()
                    )
                    .build()
                )
                .build()
            )
            response = await loop.run_in_executor(
                None, lambda: client.im.v1.message_reaction.create(request)
            )
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            return {
                "status": "added",
                "reaction_id": getattr(response.data, "reaction_id", ""),
                "message_id": message_id,
                "emoji": emoji,
            }
        except Exception as e:
            return {"error": str(e)}

    elif action == "remove":
        if not emoji:
            return {"error": "emoji is required for remove action"}
        # First, list reactions to find the reaction_id for this emoji
        try:
            from lark_oapi.api.im.v1 import (
                ListMessageReactionRequest, DeleteMessageReactionRequest,
            )

            list_builder = ListMessageReactionRequest.builder().message_id(message_id)
            list_resp = await loop.run_in_executor(
                None, lambda: client.im.v1.message_reaction.list(list_builder.build())
            )
            reaction_id = ""
            if list_resp.success() and list_resp.data:
                for item in (getattr(list_resp.data, "items", None) or []):
                    rtype = getattr(item, "reaction_type", None)
                    if rtype and getattr(rtype, "emoji_type", "") == emoji:
                        reaction_id = getattr(item, "reaction_id", "")
                        break

            if not reaction_id:
                return {"error": f"Reaction '{emoji}' not found on message"}

            del_request = (
                DeleteMessageReactionRequest.builder()
                .message_id(message_id)
                .reaction_id(reaction_id)
                .build()
            )
            del_resp = await loop.run_in_executor(
                None, lambda: client.im.v1.message_reaction.delete(del_request)
            )
            if not del_resp.success():
                return {"error": f"code={del_resp.code} msg={del_resp.msg}"}
            return {
                "status": "removed",
                "reaction_id": reaction_id,
                "message_id": message_id,
                "emoji": emoji,
            }
        except Exception as e:
            return {"error": str(e)}

    elif action == "list":
        try:
            from lark_oapi.api.im.v1 import ListMessageReactionRequest

            builder = ListMessageReactionRequest.builder().message_id(message_id)
            if page_token:
                builder = builder.page_token(page_token)
            request = builder.build()
            response = await loop.run_in_executor(
                None, lambda: client.im.v1.message_reaction.list(request)
            )
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            reactions = []
            for item in (getattr(response.data, "items", None) or []):
                rtype = getattr(item, "reaction_type", None)
                reactions.append({
                    "reaction_id": getattr(item, "reaction_id", ""),
                    "emoji": getattr(rtype, "emoji_type", "") if rtype else "",
                    "operator_id": getattr(
                        getattr(item, "operator", None), "operator_id", ""
                    ),
                    "action_time": getattr(item, "action_time", ""),
                })
            return {
                "message_id": message_id,
                "reactions": reactions,
                "has_more": getattr(response.data, "has_more", False),
                "page_token": getattr(response.data, "page_token", ""),
            }
        except Exception as e:
            return {"error": str(e)}

    return {"error": f"Unknown action: {action}"}
