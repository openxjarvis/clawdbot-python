"""JSON schemas for feishu_doc and feishu_app_scopes tools.

Mirrors: clawdbot-feishu/src/doc-tools/schemas.ts
"""
from __future__ import annotations

DOC_TOOL_NAME = "feishu_doc"
DOC_TOOL_DESCRIPTION = (
    "Read, write, create, and manage Feishu documents (Docx). "
    "Supports full markdown write, block-level editing, and document comments. "
    "Use 'read' to get content, 'write'/'append'/'create_and_write' for markdown, "
    "block ops for fine-grained edits, and comment ops to manage review threads."
)
DOC_TOOL_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": [
                "read",
                "write",
                "append",
                "create",
                "create_and_write",
                "list_blocks",
                "get_block",
                "update_block",
                "delete_block",
                "list_comments",
                "create_comment",
                "get_comment",
                "list_comment_replies",
            ],
            "description": (
                "'read': get doc title + content; "
                "'write': replace entire doc with markdown; "
                "'append': append markdown to end; "
                "'create': create empty doc; "
                "'create_and_write': create + write in one step; "
                "'list_blocks': list all blocks with types/ids; "
                "'get_block': fetch one block by id; "
                "'update_block': replace text in a block; "
                "'delete_block': remove a block; "
                "'list_comments': list doc-level comments; "
                "'create_comment': add a new comment; "
                "'get_comment': get a specific comment; "
                "'list_comment_replies': list replies to a comment."
            ),
        },
        "doc_token": {
            "type": "string",
            "description": "Feishu document token (from doc URL). Required for most actions.",
        },
        "title": {
            "type": "string",
            "description": "Document title — for 'create' and 'create_and_write'.",
        },
        "content": {
            "type": "string",
            "description": "Markdown content — for 'write', 'append', 'create_and_write', 'update_block', 'create_comment'.",
        },
        "folder_token": {
            "type": "string",
            "description": "Drive folder token to place the new document in (optional).",
        },
        "block_id": {
            "type": "string",
            "description": "Block ID — required for 'get_block', 'update_block', 'delete_block'.",
        },
        "comment_id": {
            "type": "string",
            "description": "Comment ID — required for 'get_comment', 'list_comment_replies'.",
        },
        "page_token": {
            "type": "string",
            "description": "Pagination cursor for 'list_comments', 'list_comment_replies'.",
        },
        "page_size": {
            "type": "integer",
            "description": "Page size for paginated list actions (default 50, max 100).",
        },
    },
    "required": ["action"],
}

SCOPES_TOOL_NAME = "feishu_app_scopes"
SCOPES_TOOL_DESCRIPTION = (
    "List granted and pending OAuth permission scopes for the Feishu app. "
    "Useful for debugging permission errors — shows exactly which scopes are active."
)
SCOPES_TOOL_SCHEMA: dict = {
    "type": "object",
    "properties": {},
}
