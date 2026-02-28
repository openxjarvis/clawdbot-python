"""minimax-portal-auth extension — registers with OpenClaw plugin API.

Mirrors TypeScript: openclaw/extensions/minimax-portal-auth/index.ts
"""
from __future__ import annotations



def register(api) -> None:
    # TODO: implement — see openclaw/extensions/minimax-portal-auth/index.ts for reference
    pass

plugin = {
    "id": "minimax-portal-auth",
    "name": "MiniMax Portal Auth",
    "description": "MiniMax portal authentication provider.",
    "register": register,
}
