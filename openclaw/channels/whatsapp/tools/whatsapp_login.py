"""WhatsApp login agent tool.

Allows agents to start a QR-code pairing session (start) or wait for scan
completion (wait).

Mirrors TypeScript: src/channels/plugins/agent-tools/whatsapp-login.ts
"""
from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..channel import WhatsAppChannel

logger = logging.getLogger(__name__)

TOOL_SCHEMA = {
    "name": "whatsapp_login",
    "description": (
        "Generate a WhatsApp QR code for linking, or wait for the scan to complete."
    ),
    "owner_only": True,
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["start", "wait"],
                "description": "start — begin QR pairing; wait — block until scanned or timeout.",
            },
            "account_id": {
                "type": "string",
                "description": "Account ID to operate on (default: first account).",
            },
            "timeout_ms": {
                "type": "number",
                "description": "Milliseconds to wait for scan in 'wait' action (default: 120000).",
            },
            "force": {
                "type": "boolean",
                "description": "Force a new QR even if already logged in.",
            },
        },
        "required": ["action"],
    },
}


async def run_whatsapp_login(
    params: dict[str, Any],
    channel: "WhatsAppChannel",
) -> dict[str, Any]:
    """Execute the whatsapp_login tool."""
    action = params.get("action", "start")
    account_id: str = params.get("account_id") or "default"
    timeout_ms: int = int(params.get("timeout_ms") or 120_000)
    force: bool = bool(params.get("force", False))

    bridge_client = channel._monitor.bridge_client
    if bridge_client is None:
        return {
            "content": [{"type": "text", "text": "WhatsApp bridge is not running."}],
            "details": {"connected": False},
        }

    if action == "wait":
        import asyncio

        deadline = asyncio.get_running_loop().time() + timeout_ms / 1000
        while asyncio.get_running_loop().time() < deadline:
            try:
                status = await bridge_client.get_status(account_id)
                if status.get("state") == "open":
                    return {
                        "content": [{"type": "text", "text": "WhatsApp is connected."}],
                        "details": {"connected": True},
                    }
            except Exception:
                pass
            await asyncio.sleep(3)

        return {
            "content": [{"type": "text", "text": "Timed out waiting for WhatsApp connection."}],
            "details": {"connected": False},
        }

    # action == "start"
    if not force:
        # Check if already connected
        try:
            status = await bridge_client.get_status(account_id)
            if status.get("state") == "open":
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "WhatsApp is already connected. "
                                "Use force=true to generate a new QR code."
                            ),
                        }
                    ],
                    "details": {"qr": False, "connected": True},
                }
        except Exception:
            pass

    # Start session / get QR
    try:
        await bridge_client.start_session(
            account_id,
            auth_dir=None,  # uses configured dir
            webhook_url=None,  # reuse existing webhook
        )
    except Exception:
        pass  # Session may already be started; proceed to get QR

    # Poll for QR
    import asyncio

    qr_deadline = asyncio.get_running_loop().time() + 30.0
    qr_data_url: str | None = None
    while asyncio.get_running_loop().time() < qr_deadline:
        try:
            qr_resp = await bridge_client.get_qr(account_id)
            if qr_data_url := qr_resp.get("qr"):
                break
        except Exception:
            pass
        await asyncio.sleep(2)

    if not qr_data_url:
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        "QR code not yet available. "
                        "Call whatsapp_login with action='wait' to wait for connection."
                    ),
                }
            ],
            "details": {"qr": False},
        }

    lines = [
        "WhatsApp QR code ready. Open WhatsApp → Linked Devices and scan:",
        "",
        f"![whatsapp-qr]({qr_data_url})",
    ]
    return {
        "content": [{"type": "text", "text": "\n".join(lines)}],
        "details": {"qr": True},
    }


def register(api: Any, channel: "WhatsAppChannel") -> None:
    """Register the whatsapp_login tool with the agent API."""

    async def _execute(tool_call_id: str, args: dict[str, Any]) -> dict[str, Any]:
        return await run_whatsapp_login(args, channel)

    api.register_tool(
        name=TOOL_SCHEMA["name"],
        description=TOOL_SCHEMA["description"],
        parameters=TOOL_SCHEMA["parameters"],
        execute=_execute,
        owner_only=TOOL_SCHEMA.get("owner_only", False),
    )
