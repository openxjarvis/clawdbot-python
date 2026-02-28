"""llm-task extension — registers with OpenClaw plugin API.

Mirrors TypeScript: openclaw/extensions/llm-task/index.ts
"""
from __future__ import annotations



def register(api) -> None:
    # TODO: implement — see openclaw/extensions/llm-task/index.ts for reference
    pass

plugin = {
    "id": "llm-task",
    "name": "LLM Task",
    "description": "Generic JSON-only LLM tool for structured tasks callable from workflows.",
    "register": register,
}
