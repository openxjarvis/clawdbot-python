"""feishu_doc tool — Feishu document (Docx) read/write/create.

Mirrors TypeScript: extensions/feishu/src/docx.ts
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

TOOL_NAME = "feishu_doc"
TOOL_DESCRIPTION = (
    "Read, write, or create Feishu documents. "
    "Supports reading plain text and creating new docs."
)
TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["read", "create", "append", "batch_insert"],
            "description": (
                "Action: 'read' gets content (paragraphs, headings, code, quotes, tables), "
                "'create' makes a new doc, 'append' adds a paragraph, "
                "'batch_insert' inserts multiple blocks at once."
            ),
        },
        "document_id": {
            "type": "string",
            "description": "Feishu document ID (required for read/append).",
        },
        "title": {
            "type": "string",
            "description": "Document title (for create).",
        },
        "content": {
            "type": "string",
            "description": "Text content to append or use when creating.",
        },
        "folder_token": {
            "type": "string",
            "description": "Drive folder token to create the document in.",
        },
    },
    "required": ["action"],
}


async def run_feishu_doc(
    params: dict[str, Any],
    client: Any,
) -> dict[str, Any]:
    """Execute feishu_doc tool call."""
    action = params.get("action", "read")
    doc_id = params.get("document_id", "")
    loop = asyncio.get_running_loop()

    if action == "read":
        if not doc_id:
            return {"error": "document_id is required for read"}
        try:
            from lark_oapi.api.docx.v1 import GetDocumentRequest, ListDocumentBlockRequest

            # Get doc metadata
            req = GetDocumentRequest.builder().document_id(doc_id).build()
            resp = await loop.run_in_executor(None, lambda: client.docx.v1.document.get(req))
            if not resp.success():
                return {"error": f"code={resp.code} msg={resp.msg}"}

            doc = resp.data.document
            title = getattr(doc, "title", "") if doc else ""

            # Get blocks (content)
            blocks_req = (
                ListDocumentBlockRequest.builder()
                .document_id(doc_id)
                .build()
            )
            blocks_resp = await loop.run_in_executor(
                None, lambda: client.docx.v1.document_block.list(blocks_req)
            )

            text_parts: list[str] = []
            if blocks_resp.success() and blocks_resp.data:
                for block in (blocks_resp.data.items or []):
                    block_type = getattr(block, "block_type", 0)

                    # Heading blocks (3–9) and paragraph (2)
                    if block_type == 2:  # paragraph
                        para = getattr(block, "paragraph", None)
                        if para:
                            for elem in (getattr(para, "elements", None) or []):
                                text_run = getattr(elem, "text_run", None)
                                if text_run:
                                    text_parts.append(getattr(text_run, "content", "") or "")
                        text_parts.append("\n")

                    elif 3 <= block_type <= 9:  # heading1–heading7
                        level = block_type - 2  # heading1=3 → level=1
                        # Extract text from heading elements
                        heading = (
                            getattr(block, "heading1", None)
                            or getattr(block, "heading2", None)
                            or getattr(block, "heading3", None)
                            or getattr(block, "heading4", None)
                            or getattr(block, "heading5", None)
                            or getattr(block, "heading6", None)
                            or getattr(block, "heading7", None)
                        )
                        heading_text = ""
                        if heading:
                            for elem in (getattr(heading, "elements", None) or []):
                                tr = getattr(elem, "text_run", None)
                                if tr:
                                    heading_text += getattr(tr, "content", "") or ""
                        text_parts.append(f"{'#' * level} {heading_text}\n")

                    elif block_type == 11:  # code block
                        code_block = getattr(block, "code", None)
                        code_text = ""
                        if code_block:
                            for elem in (getattr(code_block, "elements", None) or []):
                                tr = getattr(elem, "text_run", None)
                                if tr:
                                    code_text += getattr(tr, "content", "") or ""
                            lang = getattr(code_block, "language", "")
                        text_parts.append(f"```{lang}\n{code_text}\n```\n")

                    elif block_type == 12:  # quote
                        quote_block = getattr(block, "quote", None)
                        quote_text = ""
                        if quote_block:
                            for elem in (getattr(quote_block, "elements", None) or []):
                                tr = getattr(elem, "text_run", None)
                                if tr:
                                    quote_text += getattr(tr, "content", "") or ""
                        text_parts.append(f"> {quote_text}\n")

                    elif block_type == 31:  # table
                        table = getattr(block, "table", None)
                        if table:
                            rows = getattr(table, "rows", None)
                            cols = getattr(table, "columns", None)
                            text_parts.append(f"[Table: {rows}x{cols}]\n")

            return {
                "document_id": doc_id,
                "title": title,
                "content": "".join(text_parts).strip(),
            }
        except Exception as e:
            return {"error": str(e)}

    elif action == "create":
        title = params.get("title", "Untitled")
        folder_token = params.get("folder_token", "")
        try:
            from lark_oapi.api.docx.v1 import CreateDocumentRequest, CreateDocumentRequestBody

            builder = (
                CreateDocumentRequestBody.builder()
                .title(title)
            )
            if folder_token:
                builder = builder.folder_token(folder_token)

            request = (
                CreateDocumentRequest.builder()
                .request_body(builder.build())
                .build()
            )
            response = await loop.run_in_executor(None, lambda: client.docx.v1.document.create(request))
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            doc = response.data.document
            return {
                "document_id": getattr(doc, "document_id", ""),
                "title": getattr(doc, "title", title),
                "url": getattr(doc, "url", ""),
            }
        except Exception as e:
            return {"error": str(e)}

    elif action == "append":
        if not doc_id:
            return {"error": "document_id is required for append"}
        content = params.get("content", "")
        if not content:
            return {"error": "content is required for append"}
        try:
            from lark_oapi.api.docx.v1 import (
                CreateDocumentBlockChildrenRequest,
                CreateDocumentBlockChildrenRequestBody,
            )
            from lark_oapi.api.docx.v1.model import Block, BlockType, Text, TextElement, TextRun

            text_run = TextRun.builder().content(content).build()
            elem = TextElement.builder().text_run(text_run).build()
            text = Text.builder().elements([elem]).build()
            block = Block.builder().block_type(2).paragraph(text).build()

            request = (
                CreateDocumentBlockChildrenRequest.builder()
                .document_id(doc_id)
                .block_id(doc_id)  # root block
                .request_body(
                    CreateDocumentBlockChildrenRequestBody.builder()
                    .children([block])
                    .build()
                )
                .build()
            )
            response = await loop.run_in_executor(
                None, lambda: client.docx.v1.document_block_children.create(request)
            )
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            return {"document_id": doc_id, "status": "appended"}
        except Exception as e:
            return {"error": str(e)}

    elif action == "batch_insert":
        if not doc_id:
            return {"error": "document_id is required for batch_insert"}
        items = params.get("items") or []
        if not items:
            return {"error": "items list is required for batch_insert"}
        try:
            from lark_oapi.api.docx.v1 import (
                CreateDocumentBlockChildrenRequest,
                CreateDocumentBlockChildrenRequestBody,
            )
            from lark_oapi.api.docx.v1.model import Block, TextElement, TextRun, Text

            blocks = []
            for item in items:
                content = item.get("content", "")
                block_type = item.get("block_type", 2)  # default: paragraph
                text_run = TextRun.builder().content(content).build()
                elem = TextElement.builder().text_run(text_run).build()
                text = Text.builder().elements([elem]).build()
                b = Block.builder().block_type(block_type).paragraph(text).build()
                blocks.append(b)

            request = (
                CreateDocumentBlockChildrenRequest.builder()
                .document_id(doc_id)
                .block_id(doc_id)
                .request_body(
                    CreateDocumentBlockChildrenRequestBody.builder()
                    .children(blocks)
                    .build()
                )
                .build()
            )
            response = await loop.run_in_executor(
                None, lambda: client.docx.v1.document_block_children.create(request)
            )
            if not response.success():
                return {"error": f"code={response.code} msg={response.msg}"}
            return {
                "document_id": doc_id,
                "status": "inserted",
                "count": len(blocks),
            }
        except Exception as e:
            return {"error": str(e)}

    return {"error": f"Unknown action: {action}"}
