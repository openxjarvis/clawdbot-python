"""Bitable URL parser — resolves app_token and table list from a Feishu URL.

Mirrors: clawdbot-feishu/src/bitable-tools/meta.ts
"""
from __future__ import annotations

import asyncio
import re
from typing import Any

# Patterns matching /base/<app_token> and /wiki/<wiki_token>
_BASE_RE = re.compile(r"/base/([A-Za-z0-9]+)")
_WIKI_RE = re.compile(r"/wiki/([A-Za-z0-9]+)")
# Optional ?table=<table_id>
_TABLE_RE = re.compile(r"[?&]table=([A-Za-z0-9_]+)")


async def get_bitable_meta(client: Any, url: str) -> dict[str, Any]:
    """Parse a Feishu Bitable URL and return app_token + table list."""
    loop = asyncio.get_running_loop()

    # Extract table_id hint if present
    table_match = _TABLE_RE.search(url)
    table_id_hint = table_match.group(1) if table_match else None

    # Try /base/<token>
    base_match = _BASE_RE.search(url)
    if base_match:
        app_token = base_match.group(1)
        return await _fetch_table_list(client, app_token, table_id_hint)

    # Try /wiki/<token> — need to resolve the wiki node to get app_token
    wiki_match = _WIKI_RE.search(url)
    if wiki_match:
        wiki_token = wiki_match.group(1)
        try:
            from lark_oapi.api.wiki.v2 import GetSpaceNodeRequest
            resp = await loop.run_in_executor(
                None,
                lambda: client.wiki.v2.space_node.get(GetSpaceNodeRequest.builder().token(wiki_token).build()),
            )
            if resp.success() and resp.data and resp.data.node:
                app_token = getattr(resp.data.node, "obj_token", "")
                if app_token:
                    return await _fetch_table_list(client, app_token, table_id_hint)
        except Exception as e:
            raise RuntimeError(f"Could not resolve wiki node {wiki_token}: {e}") from e

    raise RuntimeError(
        f"Could not parse Bitable URL. Expected /base/<token> or /wiki/<token>. Got: {url}"
    )


async def _fetch_table_list(client: Any, app_token: str, table_id_hint: str | None) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.bitable.v1 import ListAppTableRequest

    resp = await loop.run_in_executor(
        None, lambda: client.bitable.v1.app_table.list(ListAppTableRequest.builder().app_token(app_token).build())
    )
    if not resp.success():
        raise RuntimeError(f"bitable.app_table.list failed: {resp.msg}, code={resp.code}")
    tables = [
        {
            "table_id": getattr(t, "table_id", ""),
            "name": getattr(t, "name", ""),
            "revision": getattr(t, "revision", 0),
        }
        for t in (resp.data.items or [])
    ]
    result: dict[str, Any] = {"app_token": app_token, "tables": tables}
    if table_id_hint:
        result["table_id"] = table_id_hint
        result["hint"] = "table_id extracted from URL — pass it directly to other feishu_bitable_* tools."
    else:
        result["hint"] = "Pass app_token and a table_id from 'tables' to other feishu_bitable_* tools."
    return result
