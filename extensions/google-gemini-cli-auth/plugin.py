"""google-gemini-cli-auth extension — registers with OpenClaw plugin API.

Mirrors TypeScript: openclaw/extensions/google-gemini-cli-auth/index.ts
"""
from __future__ import annotations



def register(api) -> None:
    # TODO: implement — see openclaw/extensions/google-gemini-cli-auth/index.ts for reference
    pass

plugin = {
    "id": "google-gemini-cli-auth",
    "name": "Google Gemini CLI Auth",
    "description": "Google Gemini CLI OAuth provider plugin.",
    "register": register,
}
