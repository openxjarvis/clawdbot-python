"""Register feishu_urgent tool.

Mirrors: clawdbot-feishu/src/urgent-tools/register.ts

Requires: im:message.urgent (app), im:message.urgent:sms (sms), im:message.urgent:phone (phone).
Note: sms and phone may incur tenant cost. Error code 230024 = quota exceeded.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..tools_common.api import json_result, error_result

logger = logging.getLogger(__name__)

TOOL_NAME = "feishu_urgent"
TOOL_DESCRIPTION = (
    "Send an urgent (buzz) notification for an already-sent Feishu message. "
    "Supports in-app buzz (free), SMS push, and voice call (may incur cost). "
    "The message must already exist (use its message_id from om_xxx). "
    "Requires im:message.urgent scope."
)
TOOL_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "message_id": {
            "type": "string",
            "description": "ID of the already-sent message to urgentify (om_xxx).",
        },
        "user_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of user open_ids to send the buzz to (minimum 1).",
            "minItems": 1,
        },
        "urgent_type": {
            "type": "string",
            "enum": ["app", "sms", "phone"],
            "default": "app",
            "description": "'app': in-app buzz (free); 'sms': SMS push (may cost); 'phone': voice call (may cost).",
        },
    },
    "required": ["message_id", "user_ids"],
}


async def run_feishu_urgent(params: dict[str, Any], client: Any) -> dict[str, Any]:
    message_id = params.get("message_id", "")
    user_ids = params.get("user_ids", [])
    urgent_type = params.get("urgent_type", "app")
    loop = asyncio.get_running_loop()

    if not message_id:
        return error_result("message_id is required")
    if not user_ids:
        return error_result("user_ids must have at least one entry")
    if urgent_type not in ("app", "sms", "phone"):
        return error_result(f"urgent_type must be 'app', 'sms', or 'phone', got: {urgent_type}")

    try:
        method_map = {
            "app": "urgent_app",
            "sms": "urgent_sms",
            "phone": "urgent_phone",
        }
        method_name = method_map[urgent_type]

        # Dynamic dispatch to the correct SDK method
        from lark_oapi.api.im.v1 import UrgentReceivers
        receivers = UrgentReceivers.builder().user_id_list(user_ids).build()

        if urgent_type == "app":
            from lark_oapi.api.im.v1 import UrgentAppMessageRequest
            req = UrgentAppMessageRequest.builder().message_id(message_id).user_id_type("open_id").request_body(receivers).build()
            resp = await loop.run_in_executor(None, lambda: client.im.v1.message.urgent_app(req))
        elif urgent_type == "sms":
            from lark_oapi.api.im.v1 import UrgentSmsMessageRequest
            req = UrgentSmsMessageRequest.builder().message_id(message_id).user_id_type("open_id").request_body(receivers).build()
            resp = await loop.run_in_executor(None, lambda: client.im.v1.message.urgent_sms(req))
        else:  # phone
            from lark_oapi.api.im.v1 import UrgentPhoneMessageRequest
            req = UrgentPhoneMessageRequest.builder().message_id(message_id).user_id_type("open_id").request_body(receivers).build()
            resp = await loop.run_in_executor(None, lambda: client.im.v1.message.urgent_phone(req))

        if not resp.success():
            code = getattr(resp, "code", None)
            if code == 230024:
                return error_result("Urgent notification quota exceeded (code 230024). Try again later.")
            raise RuntimeError(f"urgent_{urgent_type} failed: {resp.msg}, code={code}")

        invalid = getattr(resp.data, "invalid_user_id_list", None) or []
        return json_result({
            "ok": True,
            "message_id": message_id,
            "urgent_type": urgent_type,
            "invalid_user_list": invalid,
        })
    except Exception as e:
        logger.warning("feishu_urgent error: %s", e)
        return error_result(e)


def register_urgent_tools(api: Any) -> None:
    api.register_tool(name=TOOL_NAME, description=TOOL_DESCRIPTION, schema=TOOL_SCHEMA, handler=run_feishu_urgent)
    logger.info("Registered urgent tools: %s", TOOL_NAME)
