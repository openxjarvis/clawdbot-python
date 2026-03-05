"""Wiki action implementations.

Mirrors: clawdbot-feishu/src/wiki-tools/actions.ts
"""
from __future__ import annotations

import asyncio
from typing import Any


async def list_spaces(client: Any) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.wiki.v2 import ListSpaceRequest

    resp = await loop.run_in_executor(None, lambda: client.wiki.v2.space.list(ListSpaceRequest.builder().build()))
    if not resp.success():
        raise RuntimeError(f"wiki.space.list failed: {resp.msg}, code={resp.code}")
    spaces = [
        {
            "space_id": getattr(s, "space_id", ""),
            "name": getattr(s, "name", ""),
            "description": getattr(s, "description", ""),
            "visibility": getattr(s, "visibility", ""),
        }
        for s in (resp.data.items or [])
    ]
    hint = "Get the obj_token from 'get' action to read/edit the document with feishu_doc."
    return {"spaces": spaces, "hint": hint}


async def list_nodes(client: Any, space_id: str, parent_node_token: str | None = None, page_token: str | None = None) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.wiki.v2 import ListSpaceNodeRequest

    builder = ListSpaceNodeRequest.builder().space_id(space_id)
    if parent_node_token:
        builder = builder.parent_node_token(parent_node_token)
    if page_token:
        builder = builder.page_token(page_token)
    resp = await loop.run_in_executor(None, lambda: client.wiki.v2.space_node.list(builder.build()))
    if not resp.success():
        raise RuntimeError(f"wiki.space_node.list failed: {resp.msg}, code={resp.code}")
    nodes = [
        {
            "node_token": getattr(n, "node_token", ""),
            "obj_token": getattr(n, "obj_token", ""),
            "obj_type": getattr(n, "obj_type", ""),
            "title": getattr(n, "title", ""),
            "has_child": getattr(n, "has_child", False),
        }
        for n in (resp.data.items or [])
    ]
    return {
        "nodes": nodes,
        "has_more": getattr(resp.data, "has_more", False),
        "page_token": getattr(resp.data, "page_token", "") or "",
    }


async def get_node(client: Any, token: str) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.wiki.v2 import GetSpaceNodeRequest

    resp = await loop.run_in_executor(
        None, lambda: client.wiki.v2.space_node.get(GetSpaceNodeRequest.builder().token(token).build())
    )
    if not resp.success():
        raise RuntimeError(f"wiki.space_node.get failed: {resp.msg}, code={resp.code}")
    n = resp.data.node
    return {
        "node_token": getattr(n, "node_token", ""),
        "space_id": getattr(n, "space_id", ""),
        "obj_token": getattr(n, "obj_token", ""),
        "obj_type": getattr(n, "obj_type", ""),
        "title": getattr(n, "title", ""),
        "parent_node_token": getattr(n, "parent_node_token", ""),
        "has_child": getattr(n, "has_child", False),
        "url": getattr(n, "url", ""),
        "hint": "Use obj_token with feishu_doc to read/write the document content.",
    }


async def create_node(
    client: Any, space_id: str, title: str,
    obj_type: str = "docx", parent_node_token: str | None = None,
) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.wiki.v2 import CreateSpaceNodeRequest, CreateSpaceNodeRequestBody

    builder = (
        CreateSpaceNodeRequestBody.builder()
        .obj_type(obj_type)
        .node_type("origin")
        .title(title)
    )
    if parent_node_token:
        builder = builder.parent_node_token(parent_node_token)
    req = (
        CreateSpaceNodeRequest.builder()
        .space_id(space_id)
        .request_body(builder.build())
        .build()
    )
    resp = await loop.run_in_executor(None, lambda: client.wiki.v2.space_node.create(req))
    if not resp.success():
        raise RuntimeError(f"wiki.space_node.create failed: {resp.msg}, code={resp.code}")
    n = resp.data.node
    return {
        "node_token": getattr(n, "node_token", ""),
        "obj_token": getattr(n, "obj_token", ""),
        "obj_type": getattr(n, "obj_type", ""),
        "title": getattr(n, "title", ""),
    }


async def move_node(
    client: Any, space_id: str, node_token: str,
    target_space_id: str | None = None, target_parent_token: str | None = None,
) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.wiki.v2 import MoveSpaceNodeRequest, MoveSpaceNodeRequestBody

    builder = MoveSpaceNodeRequestBody.builder()
    if target_space_id:
        builder = builder.target_space_id(target_space_id)
    if target_parent_token:
        builder = builder.target_parent_token(target_parent_token)
    req = (
        MoveSpaceNodeRequest.builder()
        .space_id(space_id)
        .node_token(node_token)
        .request_body(builder.build())
        .build()
    )
    resp = await loop.run_in_executor(None, lambda: client.wiki.v2.space_node.move(req))
    if not resp.success():
        raise RuntimeError(f"wiki.space_node.move failed: {resp.msg}, code={resp.code}")
    n = resp.data.node if resp.data else None
    return {"success": True, "node_token": node_token, "new_parent": target_parent_token}


async def rename_node(client: Any, space_id: str, node_token: str, title: str) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.wiki.v2 import UpdateTitleSpaceNodeRequest, UpdateTitleSpaceNodeRequestBody

    req = (
        UpdateTitleSpaceNodeRequest.builder()
        .space_id(space_id)
        .node_token(node_token)
        .request_body(UpdateTitleSpaceNodeRequestBody.builder().title(title).build())
        .build()
    )
    resp = await loop.run_in_executor(None, lambda: client.wiki.v2.space_node.update_title(req))
    if not resp.success():
        raise RuntimeError(f"wiki.space_node.update_title failed: {resp.msg}, code={resp.code}")
    return {"success": True, "node_token": node_token, "title": title}
