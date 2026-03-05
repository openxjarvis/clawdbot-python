"""feishu_doc and feishu_app_scopes action implementations.

Mirrors: clawdbot-feishu/src/doc-tools/actions.ts
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_LEGACY_DOC_RE = re.compile(r"^doccn[a-zA-Z0-9]+$")


def _is_legacy_doc(token: str) -> bool:
    return bool(_LEGACY_DOC_RE.match(token))


async def read_doc(client: Any, doc_token: str) -> dict[str, Any]:
    """Read document title and content."""
    loop = asyncio.get_running_loop()
    if _is_legacy_doc(doc_token):
        return await _read_legacy_doc(client, doc_token)

    from lark_oapi.api.docx.v1 import GetDocumentRequest, ListDocumentBlockRequest

    req = GetDocumentRequest.builder().document_id(doc_token).build()
    resp = await loop.run_in_executor(None, lambda: client.docx.v1.document.get(req))
    if not resp.success():
        raise RuntimeError(f"document.get failed: {resp.msg}, code={resp.code}")
    doc = resp.data.document
    title = getattr(doc, "title", "") or ""

    blocks_req = ListDocumentBlockRequest.builder().document_id(doc_token).build()
    blocks_resp = await loop.run_in_executor(None, lambda: client.docx.v1.document_block.list(blocks_req))

    text_parts: list[str] = []
    block_count = 0
    block_types: list[int] = []

    if blocks_resp.success() and blocks_resp.data:
        for block in (blocks_resp.data.items or []):
            block_type = getattr(block, "block_type", 0)
            block_count += 1
            block_types.append(block_type)
            _extract_block_text(block, block_type, text_parts)

    return {
        "document_id": doc_token,
        "title": title,
        "content": "".join(text_parts).strip(),
        "block_count": block_count,
        "hint": "Use 'list_blocks' to see block IDs for fine-grained editing.",
    }


async def _read_legacy_doc(client: Any, doc_token: str) -> dict[str, Any]:
    """Read a legacy doc format via raw content API."""
    loop = asyncio.get_running_loop()
    import lark_oapi as lark

    req = lark.RawRequestOpts(
        method="GET",
        url=f"/open-apis/doc/v2/{doc_token}/raw_content",
        access_token_type=lark.AccessTokenType.TENANT,
    )
    resp = await loop.run_in_executor(None, lambda: client.request(req))
    if not getattr(resp, "success", lambda: True)():
        raise RuntimeError(f"legacy doc read failed: {resp.msg}")
    content = getattr(resp.data, "content", "") or ""
    return {"document_id": doc_token, "content": content, "format": "doc", "hint": "Legacy doc format."}


def _extract_block_text(block: Any, block_type: int, parts: list[str]) -> None:
    """Extract readable text from a block object and append to parts."""
    def _text_from_elements(elements: list) -> str:
        result = ""
        for elem in (elements or []):
            tr = getattr(elem, "text_run", None)
            if tr:
                result += getattr(tr, "content", "") or ""
        return result

    if block_type == 2:  # paragraph
        para = getattr(block, "paragraph", None)
        text = _text_from_elements(getattr(para, "elements", None) or []) if para else ""
        parts.append(text + "\n")
    elif 3 <= block_type <= 9:  # heading1–heading7
        level = block_type - 2
        for attr in [f"heading{i}" for i in range(1, 8)]:
            h = getattr(block, attr, None)
            if h:
                text = _text_from_elements(getattr(h, "elements", None) or [])
                parts.append(f"{'#' * level} {text}\n")
                break
    elif block_type == 11:  # code
        code = getattr(block, "code", None)
        if code:
            lang = getattr(code, "language", "") or ""
            text = _text_from_elements(getattr(code, "elements", None) or [])
            parts.append(f"```{lang}\n{text}\n```\n")
    elif block_type == 12:  # quote
        quote = getattr(block, "quote", None)
        if quote:
            text = _text_from_elements(getattr(quote, "elements", None) or [])
            parts.append(f"> {text}\n")
    elif block_type == 31:  # table
        table = getattr(block, "table", None)
        if table:
            parts.append(f"[Table: {getattr(table, 'rows', '?')}x{getattr(table, 'columns', '?')}]\n")


async def list_blocks(client: Any, doc_token: str) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.docx.v1 import ListDocumentBlockRequest

    req = ListDocumentBlockRequest.builder().document_id(doc_token).build()
    resp = await loop.run_in_executor(None, lambda: client.docx.v1.document_block.list(req))
    if not resp.success():
        raise RuntimeError(f"document_block.list failed: {resp.msg}, code={resp.code}")
    blocks = []
    for b in (resp.data.items or []):
        blocks.append({
            "block_id": getattr(b, "block_id", ""),
            "block_type": getattr(b, "block_type", 0),
            "parent_id": getattr(b, "parent_id", ""),
            "children": getattr(b, "children", []) or [],
        })
    return {"blocks": blocks, "total": len(blocks)}


async def get_block(client: Any, doc_token: str, block_id: str) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.docx.v1 import GetDocumentBlockRequest

    req = GetDocumentBlockRequest.builder().document_id(doc_token).block_id(block_id).build()
    resp = await loop.run_in_executor(None, lambda: client.docx.v1.document_block.get(req))
    if not resp.success():
        raise RuntimeError(f"document_block.get failed: {resp.msg}, code={resp.code}")
    b = resp.data.block
    return {
        "block_id": getattr(b, "block_id", ""),
        "block_type": getattr(b, "block_type", 0),
        "parent_id": getattr(b, "parent_id", ""),
        "children": getattr(b, "children", []) or [],
    }


async def update_block(client: Any, doc_token: str, block_id: str, content: str) -> dict[str, Any]:
    """Replace text content of a block."""
    loop = asyncio.get_running_loop()
    from lark_oapi.api.docx.v1 import PatchDocumentBlockRequest, PatchDocumentBlockRequestBody
    from lark_oapi.api.docx.v1.model import UpdateTextElementsOfBlockRequest, TextElement, TextRun

    text_run = TextRun.builder().content(content).build()
    elem = TextElement.builder().text_run(text_run).build()
    update = UpdateTextElementsOfBlockRequest.builder().elements([elem]).build()

    req = (
        PatchDocumentBlockRequest.builder()
        .document_id(doc_token)
        .block_id(block_id)
        .request_body(
            PatchDocumentBlockRequestBody.builder().update_text_elements(update).build()
        )
        .build()
    )
    resp = await loop.run_in_executor(None, lambda: client.docx.v1.document_block.patch(req))
    if not resp.success():
        raise RuntimeError(f"document_block.patch failed: {resp.msg}, code={resp.code}")
    return {"success": True, "block_id": block_id}


async def delete_block(client: Any, doc_token: str, block_id: str) -> dict[str, Any]:
    """Delete a block by removing it from its parent's children."""
    loop = asyncio.get_running_loop()
    from lark_oapi.api.docx.v1 import (
        GetDocumentBlockRequest,
        GetDocumentBlockChildrenRequest,
        BatchDeleteDocumentBlockChildrenRequest,
        BatchDeleteDocumentBlockChildrenRequestBody,
    )

    # Get block to find parent
    b_req = GetDocumentBlockRequest.builder().document_id(doc_token).block_id(block_id).build()
    b_resp = await loop.run_in_executor(None, lambda: client.docx.v1.document_block.get(b_req))
    if not b_resp.success():
        raise RuntimeError(f"get_block failed: {b_resp.msg}, code={b_resp.code}")
    parent_id = getattr(b_resp.data.block, "parent_id", doc_token) or doc_token

    # Get parent's children to find index
    ch_req = GetDocumentBlockChildrenRequest.builder().document_id(doc_token).block_id(parent_id).build()
    ch_resp = await loop.run_in_executor(None, lambda: client.docx.v1.document_block_children.get(ch_req))
    if not ch_resp.success():
        raise RuntimeError(f"get_block_children failed: {ch_resp.msg}, code={ch_resp.code}")
    children_ids = [getattr(c, "block_id", "") for c in (ch_resp.data.items or [])]
    if block_id not in children_ids:
        raise RuntimeError(f"block {block_id} not found in parent {parent_id}")
    idx = children_ids.index(block_id)

    del_req = (
        BatchDeleteDocumentBlockChildrenRequest.builder()
        .document_id(doc_token)
        .block_id(parent_id)
        .request_body(
            BatchDeleteDocumentBlockChildrenRequestBody.builder()
            .start_index(idx)
            .end_index(idx + 1)
            .build()
        )
        .build()
    )
    del_resp = await loop.run_in_executor(None, lambda: client.docx.v1.document_block_children.batch_delete(del_req))
    if not del_resp.success():
        raise RuntimeError(f"batch_delete failed: {del_resp.msg}, code={del_resp.code}")
    return {"success": True, "deleted_block_id": block_id}


async def list_comments(
    client: Any, doc_token: str, page_token: str | None = None, page_size: int = 50
) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.drive.v1 import ListFileCommentRequest

    builder = (
        ListFileCommentRequest.builder()
        .file_token(doc_token)
        .file_type("docx")
        .page_size(min(page_size, 100))
    )
    if page_token:
        builder = builder.page_token(page_token)
    req = builder.build()
    resp = await loop.run_in_executor(None, lambda: client.drive.v1.file_comment.list(req))
    if not resp.success():
        raise RuntimeError(f"file_comment.list failed: {resp.msg}, code={resp.code}")
    comments = []
    for c in (resp.data.items or []):
        comments.append({
            "comment_id": getattr(c, "comment_id", ""),
            "user_id": getattr(c, "user_id", ""),
            "create_time": getattr(c, "create_time", 0),
            "update_time": getattr(c, "update_time", 0),
            "is_solved": getattr(c, "is_solved", False),
            "reply_count": len(getattr(c, "reply_list", {}).get("replies", []) if isinstance(getattr(c, "reply_list", None), dict) else getattr(getattr(c, "reply_list", None), "replies", []) or []),
        })
    return {
        "comments": comments,
        "has_more": getattr(resp.data, "has_more", False),
        "page_token": getattr(resp.data, "page_token", "") or "",
    }


async def create_comment(client: Any, doc_token: str, content: str) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.drive.v1 import CreateFileCommentRequest, CreateFileCommentRequestBody
    from lark_oapi.api.drive.v1.model import FileComment, ReplyList, Reply, ReplyContent, RichTextElement

    text_elem = RichTextElement.builder().type("text_run").text_run({"text": content}).build()
    reply_content = ReplyContent.builder().elements([text_elem]).build()
    reply = Reply.builder().content(reply_content).build()
    reply_list = ReplyList.builder().replies([reply]).build()
    comment = FileComment.builder().reply_list(reply_list).build()

    req = (
        CreateFileCommentRequest.builder()
        .file_token(doc_token)
        .file_type("docx")
        .request_body(CreateFileCommentRequestBody.builder().comment(comment).build())
        .build()
    )
    resp = await loop.run_in_executor(None, lambda: client.drive.v1.file_comment.create(req))
    if not resp.success():
        raise RuntimeError(f"file_comment.create failed: {resp.msg}, code={resp.code}")
    c = resp.data.comment
    return {
        "comment_id": getattr(c, "comment_id", ""),
        "is_solved": getattr(c, "is_solved", False),
    }


async def get_comment(client: Any, doc_token: str, comment_id: str) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.drive.v1 import GetFileCommentRequest

    req = (
        GetFileCommentRequest.builder()
        .file_token(doc_token)
        .file_type("docx")
        .comment_id(comment_id)
        .build()
    )
    resp = await loop.run_in_executor(None, lambda: client.drive.v1.file_comment.get(req))
    if not resp.success():
        raise RuntimeError(f"file_comment.get failed: {resp.msg}, code={resp.code}")
    c = resp.data.comment
    return {
        "comment_id": getattr(c, "comment_id", ""),
        "user_id": getattr(c, "user_id", ""),
        "create_time": getattr(c, "create_time", 0),
        "is_solved": getattr(c, "is_solved", False),
    }


async def list_comment_replies(
    client: Any, doc_token: str, comment_id: str, page_token: str | None = None, page_size: int = 50
) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    from lark_oapi.api.drive.v1 import ListFileCommentReplyRequest

    builder = (
        ListFileCommentReplyRequest.builder()
        .file_token(doc_token)
        .file_type("docx")
        .comment_id(comment_id)
        .page_size(min(page_size, 100))
    )
    if page_token:
        builder = builder.page_token(page_token)
    req = builder.build()
    resp = await loop.run_in_executor(None, lambda: client.drive.v1.file_comment_reply.list(req))
    if not resp.success():
        raise RuntimeError(f"file_comment_reply.list failed: {resp.msg}, code={resp.code}")
    replies = []
    for r in (resp.data.items or []):
        replies.append({
            "reply_id": getattr(r, "reply_id", ""),
            "user_id": getattr(r, "user_id", ""),
            "create_time": getattr(r, "create_time", 0),
        })
    return {
        "replies": replies,
        "has_more": getattr(resp.data, "has_more", False),
        "page_token": getattr(resp.data, "page_token", "") or "",
    }


async def list_app_scopes(client: Any) -> dict[str, Any]:
    """List granted and pending OAuth scopes for the current app."""
    loop = asyncio.get_running_loop()
    try:
        from lark_oapi.api.application.v6 import ListScopeRequest
        req = ListScopeRequest.builder().build()
        resp = await loop.run_in_executor(None, lambda: client.application.v6.scope.list(req))
        if not resp.success():
            raise RuntimeError(f"scope.list failed: {resp.msg}, code={resp.code}")
        granted = [getattr(s, "scope", s) for s in (getattr(resp.data, "granted_scopes", None) or [])]
        pending = [getattr(s, "scope", s) for s in (getattr(resp.data, "pending_scopes", None) or [])]
        return {
            "granted": granted,
            "pending": pending,
            "summary": f"{len(granted)} granted, {len(pending)} pending",
        }
    except ImportError:
        return {"error": "feishu_app_scopes requires lark_oapi >= 1.x with application.v6 support"}
