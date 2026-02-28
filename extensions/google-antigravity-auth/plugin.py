"""google-antigravity-auth extension — registers with OpenClaw plugin API.

Mirrors TypeScript: openclaw/extensions/google-antigravity-auth/index.ts
"""
from __future__ import annotations



def register(api) -> None:
    # TODO: implement — see openclaw/extensions/google-antigravity-auth/index.ts for reference
    pass

plugin = {
    "id": "google-antigravity-auth",
    "name": "Google Antigravity Auth",
    "description": "Google Antigravity OAuth provider plugin.",
    "register": register,
}
