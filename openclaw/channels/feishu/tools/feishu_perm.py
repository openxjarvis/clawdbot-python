"""feishu_perm tool — Feishu permission management (sensitive, disabled by default).

Mirrors TypeScript: extensions/feishu/src/perm.ts
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

TOOL_NAME = "feishu_perm"
TOOL_DESCRIPTION = (
    "Manage Feishu file permissions: grant/revoke/list collaborators. "
    "Sensitive — disabled by default, enable with tools.perm=true."
)
TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["list", "grant", "revoke", "transfer_owner"],
            "description": "Action to perform.",
        },
        "token": {
            "type": "string",
            "description": "File/folder token.",
        },
        "type": {
            "type": "string",
            "description": "Type: 'doc', 'sheet', 'bitable', 'folder', 'file', etc.",
        },
        "member_type": {
            "type": "string",
            "enum": ["user", "chat", "department", "openid"],
            "description": "Member type for grant/revoke.",
        },
        "member_id": {
            "type": "string",
            "description": "Member ID (user_id, chat_id, etc.).",
        },
        "perm": {
            "type": "string",
            "enum": ["view", "edit", "full_access"],
            "description": "Permission level to grant.",
        },
    },
    "required": ["action", "token", "type"],
}


async def run_feishu_perm(
    params: dict[str, Any],
    client: Any,
) -> dict[str, Any]:
    """Execute feishu_perm tool call."""
    action = params.get("action", "list")
    token = params.get("token", "")
    file_type = params.get("type", "doc")
    loop = asyncio.get_running_loop()

    if action == "list":
        try:
            from lark_oapi.api.drive.v1 import ListPermissionMemberRequest

            request = (
                ListPermissionMemberRequest.builder()
                .token(token)
                .type(file_type)
                .build()
            )
            response = await loop.run_in_executor(
                None, lambda: client.drive.v1.permission_member.list(request)
            )
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            members = []
            for m in (response.data.members or []):
                members.append({
                    "member_type": getattr(m, "member_type", ""),
                    "member_id": getattr(m, "member_id", ""),
                    "perm": getattr(m, "perm", ""),
                    "name": getattr(m, "name", ""),
                })
            return {"token": token, "type": file_type, "members": members}
        except Exception as e:
            return {"error": str(e)}

    elif action == "grant":
        member_type = params.get("member_type", "user")
        member_id = params.get("member_id", "")
        perm = params.get("perm", "view")
        if not member_id:
            return {"error": "member_id is required"}
        try:
            from lark_oapi.api.drive.v1 import CreatePermissionMemberRequest, CreatePermissionMemberRequestBody
            from lark_oapi.api.drive.v1.model import BaseMember

            member = BaseMember.builder().member_type(member_type).member_id(member_id).perm(perm).build()
            request = (
                CreatePermissionMemberRequest.builder()
                .token(token)
                .type(file_type)
                .need_notification(False)
                .request_body(
                    CreatePermissionMemberRequestBody.builder()
                    .member(member)
                    .build()
                )
                .build()
            )
            response = await loop.run_in_executor(
                None, lambda: client.drive.v1.permission_member.create(request)
            )
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            return {"status": "granted", "token": token, "member_id": member_id, "perm": perm}
        except Exception as e:
            return {"error": str(e)}

    elif action == "revoke":
        member_type = params.get("member_type", "user")
        member_id = params.get("member_id", "")
        if not member_id:
            return {"error": "member_id is required"}
        try:
            from lark_oapi.api.drive.v1 import DeletePermissionMemberRequest

            request = (
                DeletePermissionMemberRequest.builder()
                .token(token)
                .type(file_type)
                .member_type(member_type)
                .member_id(member_id)
                .build()
            )
            response = await loop.run_in_executor(
                None, lambda: client.drive.v1.permission_member.delete(request)
            )
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            return {"status": "revoked", "token": token, "member_id": member_id}
        except Exception as e:
            return {"error": str(e)}

    elif action == "transfer_owner":
        member_type = params.get("member_type", "user")
        member_id = params.get("member_id", "")
        if not member_id:
            return {"error": "member_id is required for transfer_owner"}
        try:
            from lark_oapi.api.drive.v1 import TransferOwnerPermissionRequest, TransferOwnerPermissionRequestBody
            from lark_oapi.api.drive.v1.model import BaseMember

            member = BaseMember.builder().member_type(member_type).member_id(member_id).build()
            request = (
                TransferOwnerPermissionRequest.builder()
                .token(token)
                .type(file_type)
                .request_body(
                    TransferOwnerPermissionRequestBody.builder()
                    .owner(member)
                    .build()
                )
                .build()
            )
            response = await loop.run_in_executor(
                None, lambda: client.drive.v1.permission_member.transfer_owner(request)
            )
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            return {"status": "transferred", "token": token, "new_owner": member_id}
        except Exception as e:
            return {"error": str(e)}

    return {"error": f"Unknown action: {action}"}
