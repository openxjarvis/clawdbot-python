"""zalouser extension — registers with OpenClaw plugin API.

Mirrors TypeScript: openclaw/extensions/zalouser/index.ts
"""
from __future__ import annotations



def register(api) -> None:
    # TODO: implement — see openclaw/extensions/zalouser/index.ts for reference
    pass

plugin = {
    "id": "zalouser",
    "name": "Zalo User",
    "description": "Zalo personal user channel integration.",
    "register": register,
}
