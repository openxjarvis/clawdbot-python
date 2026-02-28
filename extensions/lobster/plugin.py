"""lobster extension — registers with OpenClaw plugin API.

Mirrors TypeScript: openclaw/extensions/lobster/index.ts
"""
from __future__ import annotations



def register(api) -> None:
    # TODO: implement — see openclaw/extensions/lobster/index.ts for reference
    pass

plugin = {
    "id": "lobster",
    "name": "Lobster",
    "description": "Typed workflow tool with resumable approvals.",
    "register": register,
}
