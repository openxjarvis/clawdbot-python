"""qwen-portal-auth extension — registers with OpenClaw plugin API.

Mirrors TypeScript: openclaw/extensions/qwen-portal-auth/index.ts
"""
from __future__ import annotations



def register(api) -> None:
    # TODO: implement — see openclaw/extensions/qwen-portal-auth/index.ts for reference
    pass

plugin = {
    "id": "qwen-portal-auth",
    "name": "Qwen Portal Auth",
    "description": "Qwen portal OAuth provider plugin.",
    "register": register,
}
