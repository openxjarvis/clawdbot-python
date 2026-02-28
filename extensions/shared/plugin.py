"""Shared extension utilities — helpers used across other extensions.

Mirrors TypeScript: openclaw/extensions/shared/

This package provides shared utilities (target resolution, test helpers, etc.)
and does not register any plugin capabilities itself.
"""
from __future__ import annotations



def register(api) -> None:
    # Shared utilities only — nothing to register
    pass

plugin = {
    "id": "shared",
    "name": "Shared Utilities",
    "description": "Shared extension utilities (internal).",
    "register": register,
}
