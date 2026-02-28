"""Device pairing extension — QR-based device pairing and approval.

Mirrors TypeScript: openclaw/extensions/device-pair/index.ts
"""
from __future__ import annotations



def register(api) -> None:
    # TODO: implement device pairing CLI commands (list, approve) and HTTP handler
    # See openclaw/extensions/device-pair/index.ts for reference
    pass

plugin = {
    "id": "device-pair",
    "name": "Device Pairing",
    "description": "Generate setup codes and approve device pairing requests.",
    "register": register,
}
