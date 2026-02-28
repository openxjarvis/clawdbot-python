"""Memory (Core) extension — file-backed memory search and get tools.

Mirrors TypeScript: openclaw/extensions/memory-core/index.ts

Registers:
- ``memory_search`` tool — semantic/substring search over stored memories
- ``memory_get`` tool   — retrieve a specific memory entry by ID
- ``memory`` CLI command — manage stored memories from the CLI
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def _memory_dir(workspace_dir: str | None = None) -> Path:
    if workspace_dir:
        d = Path(workspace_dir) / ".openclaw" / "memory"
    else:
        d = Path.home() / ".openclaw" / "memory"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_memories(workspace_dir: str | None = None) -> list[dict[str, Any]]:
    store = _memory_dir(workspace_dir) / "memories.json"
    if not store.exists():
        return []
    try:
        data = json.loads(store.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_memories(memories: list[dict[str, Any]], workspace_dir: str | None = None) -> None:
    store = _memory_dir(workspace_dir) / "memories.json"
    store.write_text(json.dumps(memories, indent=2))


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _make_memory_search_tool(workspace_dir: str | None = None) -> dict[str, Any]:
    async def execute(
        tool_call_id: str,
        params: dict[str, Any],
        signal: Any = None,
        ctx: Any = None,
    ) -> dict[str, Any]:
        query: str = params.get("query", "").lower().strip()
        limit: int = int(params.get("limit", 10))

        memories = _load_memories(workspace_dir)
        if not query:
            results = memories[-limit:]
        else:
            results = [
                m for m in memories
                if query in m.get("content", "").lower()
                or query in m.get("tags", "")
            ][:limit]

        return {
            "results": results,
            "total": len(results),
            "query": query,
        }

    return {
        "name": "memory_search",
        "description": (
            "Search through stored memories. "
            "Use this to recall past conversations, facts, or notes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (substring match against memory content)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default 10)",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
        "execute": execute,
    }


def _make_memory_get_tool(workspace_dir: str | None = None) -> dict[str, Any]:
    async def execute(
        tool_call_id: str,
        params: dict[str, Any],
        signal: Any = None,
        ctx: Any = None,
    ) -> dict[str, Any]:
        memory_id: str = params.get("id", "").strip()
        memories = _load_memories(workspace_dir)
        for m in memories:
            if m.get("id") == memory_id:
                return {"memory": m, "found": True}
        return {"memory": None, "found": False, "id": memory_id}

    return {
        "name": "memory_get",
        "description": "Retrieve a specific memory entry by its ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "The unique memory ID returned by memory_search",
                },
            },
            "required": ["id"],
        },
        "execute": execute,
    }


# ---------------------------------------------------------------------------
# Plugin registration
# ---------------------------------------------------------------------------

def register(api) -> None:
    """Register memory tools with the PluginApi.

    api.register_tool() accepts a factory callable (ctx) -> tool | list[tool]
    and opts dict with 'names'. We pass a simple object with an execute method.
    Mirrors TS: api.registerTool((ctx) => [memorySearchTool, memoryGetTool], {...})
    """
    workspace_dir: str | None = None
    if hasattr(api, "context") and api.context:
        workspace_dir = getattr(api.context, "workspace_dir", None)

    search_def = _make_memory_search_tool(workspace_dir)
    get_def = _make_memory_get_tool(workspace_dir)

    # Register as factory functions — PluginApi stores these in PluginToolRegistration.factory
    def memory_tool_factory(ctx: Any = None) -> list[Any]:
        return [search_def, get_def]

    api.register_tool(
        memory_tool_factory,
        {"names": [search_def["name"], get_def["name"]]},
    )

    # Register CLI command
    def memory_cli_registrar(program: Any = None) -> None:
        # TODO: implement full memory CLI — see openclaw/extensions/memory-core/index.ts
        pass

    api.register_cli(
        memory_cli_registrar,
        {"commands": ["memory"]},
    )

plugin = {
    "id": "memory-core",
    "name": "Memory (Core)",
    "description": "File-backed memory search and get tools with CLI management.",
    "register": register,
}
