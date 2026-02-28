"""talk-voice extension — registers with OpenClaw plugin API.

Mirrors TypeScript: openclaw/extensions/talk-voice/index.ts
"""
from __future__ import annotations



def register(api) -> None:
    # TODO: implement — see openclaw/extensions/talk-voice/index.ts for reference
    pass

plugin = {
    "id": "talk-voice",
    "name": "Talk Voice",
    "description": "Manage Talk voice selection (list/set).",
    "register": register,
}
