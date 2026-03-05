"""Register feishu_perm tool (disabled by default — sensitive).

Mirrors: clawdbot-feishu/src/perm-tools/register.ts
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..tools_common.api import json_result, error_result

logger = logging.getLogger(__name__)

TOOL_NAME = "feishu_perm"
TOOL_DESCRIPTION = (
    "Manage Feishu file/folder permissions: list members, add (grant) access, remove (revoke) access. "
    "SENSITIVE — disabled by default. Supported types: doc, docx, sheet, bitable, folder, file, wiki, mindnote. "
    "Member types: email, openid, userid, unionid, openchat, opendepartmentid."
)
TOOL_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["list", "add", "remove"],
            "description": "'list': list current members; 'add': grant access; 'remove': revoke access.",
        },
        "token": {"type": "string", "description": "File/folder token."},
        "type": {
            "type": "string",
            "enum": ["doc", "docx", "sheet", "bitable", "folder", "file", "wiki", "mindnote"],
            "description": "Resource type.",
        },
        "member_type": {
            "type": "string",
            "enum": ["email", "openid", "userid", "unionid", "openchat", "opendepartmentid"],
            "description": "Member identifier type (required for add/remove).",
        },
        "member_id": {"type": "string", "description": "Member ID corresponding to member_type."},
        "perm": {
            "type": "string",
            "enum": ["view", "edit", "full_access"],
            "description": "Permission level to grant (required for add).",
        },
    },
    "required": ["action", "token", "type"],
}


async def run_feishu_perm(params: dict[str, Any], client: Any) -> dict[str, Any]:
    action = params.get("action", "list")
    token = params.get("token", "")
    file_type = params.get("type", "doc")
    loop = asyncio.get_running_loop()

    try:
        if action == "list":
            from lark_oapi.api.drive.v1 import ListPermissionMemberRequest
            req = ListPermissionMemberRequest.builder().token(token).type(file_type).build()
            resp = await loop.run_in_executor(None, lambda: client.drive.v1.permission_member.list(req))
            if not resp.success():
                raise RuntimeError(f"permission_member.list failed: {resp.msg}, code={resp.code}")
            members = [
                {
                    "member_type": getattr(m, "member_type", ""),
                    "member_id": getattr(m, "member_id", ""),
                    "perm": getattr(m, "perm", ""),
                    "name": getattr(m, "name", ""),
                }
                for m in (resp.data.members or [])
            ]
            return json_result({"token": token, "type": file_type, "members": members})

        elif action == "add":
            member_type = params.get("member_type", "openid")
            member_id = params.get("member_id", "")
            perm = params.get("perm", "view")
            if not member_id:
                return error_result("member_id is required for add")
            from lark_oapi.api.drive.v1 import CreatePermissionMemberRequest, CreatePermissionMemberRequestBody
            from lark_oapi.api.drive.v1.model import BaseMember
            member = BaseMember.builder().member_type(member_type).member_id(member_id).perm(perm).build()
            req = (
                CreatePermissionMemberRequest.builder()
                .token(token).type(file_type).need_notification(False)
                .request_body(CreatePermissionMemberRequestBody.builder().member(member).build())
                .build()
            )
            resp = await loop.run_in_executor(None, lambda: client.drive.v1.permission_member.create(req))
            if not resp.success():
                raise RuntimeError(f"permission_member.create failed: {resp.msg}, code={resp.code}")
            return json_result({"success": True, "token": token, "member_id": member_id, "perm": perm})

        elif action == "remove":
            member_type = params.get("member_type", "openid")
            member_id = params.get("member_id", "")
            if not member_id:
                return error_result("member_id is required for remove")
            from lark_oapi.api.drive.v1 import DeletePermissionMemberRequest
            req = (
                DeletePermissionMemberRequest.builder()
                .token(token).type(file_type).member_type(member_type).member_id(member_id)
                .build()
            )
            resp = await loop.run_in_executor(None, lambda: client.drive.v1.permission_member.delete(req))
            if not resp.success():
                raise RuntimeError(f"permission_member.delete failed: {resp.msg}, code={resp.code}")
            return json_result({"success": True, "token": token, "member_id": member_id})

        return error_result(f"Unknown action: {action}")
    except Exception as e:
        logger.warning("feishu_perm[%s] error: %s", action, e)
        return error_result(e)


def register_perm_tools(api: Any) -> None:
    """Register feishu_perm. Disabled by default — sensitive operation."""
    api.register_tool(name=TOOL_NAME, description=TOOL_DESCRIPTION, schema=TOOL_SCHEMA, handler=run_feishu_perm)
    logger.info("Registered perm tools: %s (disabled by default)", TOOL_NAME)
