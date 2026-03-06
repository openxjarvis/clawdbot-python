"""Feishu Document Write Service — converts Markdown to Feishu docx blocks.

Mirrors: clawdbot-feishu/src/doc-write-service.ts

Pipeline:
1. client.docx.v1.document.convert() — Feishu converts Markdown → block list
2. Optionally clear existing content (write mode)
3. Insert blocks in batches of 50 with exponential-backoff retry
4. Tables are inserted in two passes: skeleton first, then cell children
"""
from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Retry policy for block creation (matches TS RETRYABLE_CREATE_ERROR_CODES)
_RETRYABLE_CREATE_CODES = frozenset([429, 1254290, 1254291, 1255040])
_CREATE_BACKOFF_MS = [350, 900, 1800, 3600]
_BATCH_SIZE = 50
_TABLE_BLOCK_TYPE = 31
_TABLE_CELL_TYPE = 32


@dataclass
class CreateDocResult:
    document_id: str
    title: str
    url: str


@dataclass
class WriteDocResult:
    success: bool
    blocks_deleted: int
    blocks_added: int
    warning: str | None = None


@dataclass
class AppendDocResult:
    success: bool
    blocks_added: int
    block_ids: list[str]
    warning: str | None = None


@dataclass
class CreateAndWriteDocResult:
    document_id: str
    title: str
    url: str
    blocks_added: int
    warning: str | None = None


async def create_doc(
    client: Any,
    title: str,
    folder_token: str | None = None,
) -> CreateDocResult:
    """Create a new empty Feishu document."""
    loop = asyncio.get_running_loop()
    from lark_oapi.api.docx.v1 import CreateDocumentRequest, CreateDocumentRequestBody

    builder = CreateDocumentRequestBody.builder().title(title)
    if folder_token:
        builder = builder.folder_token(folder_token)
    request = CreateDocumentRequest.builder().request_body(builder.build()).build()
    resp = await loop.run_in_executor(None, lambda: client.docx.v1.document.create(request))
    if not resp.success():
        raise RuntimeError(f"create_doc failed: {resp.msg}, code={resp.code}")
    doc = resp.data.document
    return CreateDocResult(
        document_id=getattr(doc, "document_id", ""),
        title=getattr(doc, "title", title),
        url=getattr(doc, "url", ""),
    )


async def write_doc(
    client: Any,
    doc_token: str,
    markdown: str,
) -> WriteDocResult:
    """Replace all content in a Feishu document with the given Markdown."""
    blocks_deleted = await _clear_document(client, doc_token)
    blocks_added, _, warning = await _convert_and_insert(client, doc_token, markdown, append=False)
    return WriteDocResult(
        success=True,
        blocks_deleted=blocks_deleted,
        blocks_added=blocks_added,
        warning=warning,
    )


async def append_doc(
    client: Any,
    doc_token: str,
    markdown: str,
) -> AppendDocResult:
    """Append Markdown content to the end of a Feishu document."""
    blocks_added, block_ids, warning = await _convert_and_insert(client, doc_token, markdown, append=True)
    return AppendDocResult(
        success=True,
        blocks_added=blocks_added,
        block_ids=block_ids,
        warning=warning,
    )


async def create_and_write_doc(
    client: Any,
    title: str,
    markdown: str,
    folder_token: str | None = None,
) -> CreateAndWriteDocResult:
    """Atomically create a new document and write Markdown content into it."""
    doc = await create_doc(client, title, folder_token)
    blocks_added, _, warning = await _convert_and_insert(client, doc.document_id, markdown, append=False)
    return CreateAndWriteDocResult(
        document_id=doc.document_id,
        title=doc.title,
        url=doc.url,
        blocks_added=blocks_added,
        warning=warning,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _clear_document(client: Any, doc_token: str) -> int:
    """Delete all top-level blocks from a document. Returns number deleted."""
    loop = asyncio.get_running_loop()
    from lark_oapi.api.docx.v1 import (
        ListDocumentBlockRequest,
        BatchDeleteDocumentBlockChildrenRequest,
        BatchDeleteDocumentBlockChildrenRequestBody,
    )

    req = ListDocumentBlockRequest.builder().document_id(doc_token).build()
    resp = await loop.run_in_executor(None, lambda: client.docx.v1.document_block.list(req))
    if not resp.success() or not resp.data:
        return 0
    items = resp.data.items or []
    # Count direct children of root (parent_id == doc_token)
    children = [b for b in items if getattr(b, "parent_id", None) == doc_token]
    count = len(children)
    if count == 0:
        return 0

    del_req = (
        BatchDeleteDocumentBlockChildrenRequest.builder()
        .document_id(doc_token)
        .block_id(doc_token)
        .request_body(
            BatchDeleteDocumentBlockChildrenRequestBody.builder()
            .start_index(0)
            .end_index(count)
            .build()
        )
        .build()
    )
    del_resp = await loop.run_in_executor(None, lambda: client.docx.v1.document_block_children.batch_delete(del_req))
    if not del_resp.success():
        logger.warning("clear_document partial failure: %s", del_resp.msg)
    return count


async def _convert_and_insert(
    client: Any,
    doc_token: str,
    markdown: str,
    append: bool,
) -> tuple[int, list[str], str | None]:
    """Convert Markdown to blocks and insert them. Returns (count, block_ids, warning)."""
    try:
        blocks, first_level_ids = await _convert_markdown(client, doc_token, markdown)
    except Exception as e:
        logger.warning("markdown convert failed, falling back to plain paragraph: %s", e)
        # Fallback: insert as a single paragraph block
        count, ids = await _insert_plain_paragraph(client, doc_token, markdown)
        return count, ids, f"Markdown convert unavailable, inserted as plain text: {e}"

    if not blocks:
        return 0, [], None

    ordered = _reorder_blocks(blocks, first_level_ids)
    block_map = {getattr(b, "block_id", ""): b for b in blocks}
    block_ids = await _insert_blocks_preserving_tables(client, doc_token, ordered, block_map)
    return len(block_ids), block_ids, None


async def _convert_markdown(client: Any, doc_token: str, markdown: str) -> tuple[list[Any], list[str]]:
    """Call Feishu's document.convert API to turn Markdown into block structures."""
    loop = asyncio.get_running_loop()
    # Import the convert request — may not exist in older SDK versions
    try:
        from lark_oapi.api.docx.v1 import ConvertDocumentRequest, ConvertDocumentRequestBody
    except ImportError as e:
        raise RuntimeError(f"lark_oapi SDK does not support document.convert: {e}") from e

    body = ConvertDocumentRequestBody.builder().content_type("markdown").content(markdown).build()
    # Note: ConvertDocumentRequest.builder() has no document_id() method —
    # this API converts content standalone and doesn't require an existing document.
    req = ConvertDocumentRequest.builder().request_body(body).build()
    resp = await loop.run_in_executor(None, lambda: client.docx.v1.document.convert(req))
    if not resp.success():
        raise RuntimeError(f"document.convert failed: {resp.msg}, code={resp.code}")

    data = resp.data
    blocks = getattr(data, "blocks", None) or []
    first_level_ids: list[str] = getattr(data, "first_level_block_ids", None) or []
    return blocks, first_level_ids


def _reorder_blocks(blocks: list[Any], first_level_ids: list[str]) -> list[Any]:
    """Reorder blocks according to first_level_block_ids ordering."""
    if not first_level_ids:
        return blocks
    block_map = {getattr(b, "block_id", ""): b for b in blocks}
    ordered = [block_map[bid] for bid in first_level_ids if bid in block_map]
    return ordered


def _strip_block_metadata(block: Any) -> dict[str, Any]:
    """Convert block object to a clean dict, stripping server-assigned fields."""
    if isinstance(block, dict):
        d = {k: v for k, v in block.items() if k not in ("block_id", "parent_id", "children")}
        # Strip merge_info from table property (TS does this too)
        if "table" in d and isinstance(d["table"], dict):
            d["table"] = {k: v for k, v in d["table"].items() if k != "merge_info"}
        return d
    # lark_oapi model object — convert via __dict__ or to_dict if available
    if hasattr(block, "to_dict"):
        raw = block.to_dict()
    elif hasattr(block, "__dict__"):
        raw = {k: v for k, v in block.__dict__.items() if not k.startswith("_")}
    else:
        raw = {}
    return _strip_block_metadata(raw)


async def _insert_blocks_preserving_tables(
    client: Any,
    doc_token: str,
    ordered_blocks: list[Any],
    block_map: dict[str, Any],
) -> list[str]:
    """Insert top-level blocks, handling table blocks specially."""
    loop = asyncio.get_running_loop()
    all_ids: list[str] = []

    non_table: list[Any] = []
    non_table_positions: list[int] = []  # position in ordered_blocks

    for idx, block in enumerate(ordered_blocks):
        block_type = getattr(block, "block_type", None) or (
            block.get("block_type") if isinstance(block, dict) else None
        )
        if block_type == _TABLE_BLOCK_TYPE:
            # Flush accumulated non-table blocks first
            if non_table:
                ids = await _insert_blocks_in_batches(client, doc_token, doc_token, non_table)
                all_ids.extend(ids)
                non_table = []
                non_table_positions = []
            # Insert table
            table_ids = await _insert_table_with_cells(client, doc_token, block, block_map)
            all_ids.extend(table_ids)
        else:
            # Skip table cell blocks at top level (they are inserted as children of tables)
            if block_type != _TABLE_CELL_TYPE:
                non_table.append(block)
                non_table_positions.append(idx)

    if non_table:
        ids = await _insert_blocks_in_batches(client, doc_token, doc_token, non_table)
        all_ids.extend(ids)

    return all_ids


async def _insert_blocks_in_batches(
    client: Any,
    doc_token: str,
    parent_block_id: str,
    blocks: list[Any],
    index: int | None = None,
) -> list[str]:
    """Insert blocks as children of parent_block_id in batches of BATCH_SIZE with retry."""
    loop = asyncio.get_running_loop()
    from lark_oapi.api.docx.v1 import (
        CreateDocumentBlockChildrenRequest,
        CreateDocumentBlockChildrenRequestBody,
    )

    all_ids: list[str] = []
    for i in range(0, len(blocks), _BATCH_SIZE):
        batch = blocks[i : i + _BATCH_SIZE]
        clean = [_strip_block_metadata(b) for b in batch]

        for attempt, delay in enumerate([0] + _CREATE_BACKOFF_MS):
            if delay:
                await asyncio.sleep(delay / 1000 * (1 + 0.2 * (random.random() * 2 - 1)))
            try:
                body_builder = CreateDocumentBlockChildrenRequestBody.builder().children(clean)
                if index is not None:
                    body_builder = body_builder.index(index + i)
                req = (
                    CreateDocumentBlockChildrenRequest.builder()
                    .document_id(doc_token)
                    .block_id(parent_block_id)
                    .request_body(body_builder.build())
                    .build()
                )
                resp = await loop.run_in_executor(None, lambda: client.docx.v1.document_block_children.create(req))
                if resp.success():
                    for child in (resp.data.children or []):
                        bid = getattr(child, "block_id", "")
                        if bid:
                            all_ids.append(bid)
                    break
                code = getattr(resp, "code", None)
                if code in _RETRYABLE_CREATE_CODES and attempt < len(_CREATE_BACKOFF_MS):
                    logger.debug("Retrying block insert (attempt %d): code=%s", attempt + 1, code)
                    continue
                raise RuntimeError(f"insert_blocks failed: {resp.msg}, code={code}")
            except RuntimeError:
                raise
            except Exception as e:
                if attempt < len(_CREATE_BACKOFF_MS):
                    logger.debug("Retrying block insert after exception: %s", e)
                    continue
                raise

    return all_ids


async def _insert_table_with_cells(
    client: Any,
    doc_token: str,
    table_block: Any,
    block_map: dict[str, Any],
) -> list[str]:
    """Insert a table block, then populate its cells. Returns inserted block ids."""
    loop = asyncio.get_running_loop()
    from lark_oapi.api.docx.v1 import (
        CreateDocumentBlockChildrenRequest,
        CreateDocumentBlockChildrenRequestBody,
    )

    # 1) Insert table skeleton (without cell contents)
    table_clean = _strip_block_metadata(table_block)
    req = (
        CreateDocumentBlockChildrenRequest.builder()
        .document_id(doc_token)
        .block_id(doc_token)
        .request_body(
            CreateDocumentBlockChildrenRequestBody.builder().children([table_clean]).build()
        )
        .build()
    )
    resp = await loop.run_in_executor(None, lambda: client.docx.v1.document_block_children.create(req))
    if not resp.success():
        raise RuntimeError(f"insert_table skeleton failed: {resp.msg}")

    dst_table_id = getattr(resp.data.children[0], "block_id", "") if resp.data.children else ""
    if not dst_table_id:
        return []

    # 2) Map source cell ids → destination cell ids from the response
    src_children = getattr(table_block, "children", None) or (
        table_block.get("children") if isinstance(table_block, dict) else []
    ) or []
    dst_children_objs = getattr(resp.data.children[0], "children", None) or []
    dst_cell_ids = [getattr(c, "block_id", "") for c in dst_children_objs]

    for src_cell_id, dst_cell_id in zip(src_children, dst_cell_ids):
        if not dst_cell_id:
            continue
        src_cell = block_map.get(src_cell_id)
        if not src_cell:
            continue
        cell_children_ids = getattr(src_cell, "children", None) or (
            src_cell.get("children") if isinstance(src_cell, dict) else []
        ) or []
        cell_child_blocks = [block_map[cid] for cid in cell_children_ids if cid in block_map]
        if cell_child_blocks:
            await _insert_blocks_in_batches(client, doc_token, dst_cell_id, cell_child_blocks)

    return [dst_table_id]


async def _insert_plain_paragraph(client: Any, doc_token: str, content: str) -> tuple[int, list[str]]:
    """Fallback: insert content as a single plain paragraph."""
    loop = asyncio.get_running_loop()
    from lark_oapi.api.docx.v1 import (
        CreateDocumentBlockChildrenRequest,
        CreateDocumentBlockChildrenRequestBody,
    )
    from lark_oapi.api.docx.v1.model import Block, Text, TextElement, TextRun

    text_run = TextRun.builder().content(content).build()
    elem = TextElement.builder().text_run(text_run).build()
    text = Text.builder().elements([elem]).build()
    # Block.builder() uses .text() not .paragraph() in the installed lark_oapi version.
    block = Block.builder().block_type(2).text(text).build()

    req = (
        CreateDocumentBlockChildrenRequest.builder()
        .document_id(doc_token)
        .block_id(doc_token)
        .request_body(
            CreateDocumentBlockChildrenRequestBody.builder().children([block]).build()
        )
        .build()
    )
    resp = await loop.run_in_executor(None, lambda: client.docx.v1.document_block_children.create(req))
    if not resp.success():
        raise RuntimeError(f"insert_paragraph failed: {resp.msg}")
    ids = [getattr(c, "block_id", "") for c in (resp.data.children or [])]
    return len(ids), ids
