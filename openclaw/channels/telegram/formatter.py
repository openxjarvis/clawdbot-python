"""Message formatting for Telegram - aligned with TypeScript format.ts"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

# ---------------------------------------------------------------------------
# File reference TLD protection
# ---------------------------------------------------------------------------
# These file extensions look like country-code TLDs to Telegram, causing it to
# generate unwanted domain-registrar link previews for things like README.md.
# Mirrors TS FILE_EXTENSIONS_WITH_TLD in src/telegram/format.ts.
FILE_EXTENSIONS_WITH_TLD: frozenset[str] = frozenset([
    "md",   # Markdown (Moldova) — very common in repos
    "go",   # Go language (Equatorial Guinea)
    "py",   # Python (Paraguay)
    "pl",   # Perl (Poland)
    "sh",   # Shell (Saint Helena)
    "am",   # Automake (Armenia)
    "at",   # Assembly (Austria)
    "be",   # Backend (Belgium)
    "cc",   # C++ source (Cocos Islands)
    "rs",   # Rust (Serbia)
    "rb",   # Ruby (???)
    "ts",   # TypeScript (???)
])

_TLD_FILE_RE = re.compile(
    r'\b([\w\-/][\w\-./]*\.(?:' + '|'.join(sorted(FILE_EXTENSIONS_WITH_TLD)) + r'))\b',
    re.IGNORECASE,
)


def wrap_file_references_in_html(html: str) -> str:
    """Wrap bare filename.ext references in <code> tags to prevent Telegram
    from treating common file extensions as TLDs and generating link previews.

    Only wraps text that is not already inside a <code> or <pre> block.
    Mirrors TS wrapFileReferencesInHtml() in src/telegram/format.ts.
    """
    # Split on already-code-formatted blocks; only wrap outside those blocks.
    parts = re.split(r'(<(?:code|pre)[^>]*>.*?</(?:code|pre)>)', html, flags=re.DOTALL)
    result: List[str] = []
    for part in parts:
        if re.match(r'<(?:code|pre)', part, re.IGNORECASE):
            result.append(part)  # already formatted — leave as-is
        else:
            result.append(_TLD_FILE_RE.sub(lambda m: f"<code>{m.group(0)}</code>", part))
    return "".join(result)


def escape_html(text: str) -> str:
    """Escape HTML special characters for safe use in Telegram HTML messages."""
    if not text:
        return text
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text


def escape_html_attr(text: str) -> str:
    """Escape HTML special characters for use in HTML attribute values."""
    text = escape_html(text)
    text = text.replace('"', "&quot;")
    return text


@dataclass
class TelegramChunk:
    """A single formatted chunk ready to send to Telegram."""
    html: str
    plain: str
    length: int


def markdown_to_telegram_chunks(
    text: str,
    limit: int = 4096,
) -> List["TelegramChunk"]:
    """
    Convert Markdown text to a list of Telegram-ready HTML chunks.

    Each chunk fits within *limit* characters of the HTML output.
    File references with TLD-like extensions (.md, .go, .py, .sh, etc.) are
    wrapped in <code> to prevent Telegram from treating them as domain links.

    Args:
        text: Markdown input text.
        limit: Maximum characters per chunk (Telegram limit = 4096).

    Returns:
        List of TelegramChunk objects.
    """
    html = wrap_file_references_in_html(markdown_to_html(text))
    raw_chunks = chunk_message(html, max_length=limit)
    return [
        TelegramChunk(html=c, plain=re.sub(r"<[^>]+>", "", c), length=len(c))
        for c in raw_chunks
    ]


def markdown_to_html(text: str) -> str:
    """Convert Markdown to Telegram HTML.

    Telegram supports: <b>, <i>, <u>, <s>, <code>, <pre><code>, <a href="">,
    <blockquote>, <tg-spoiler>.

    Mirrors TS renderTelegramHtml() in src/telegram/format.ts:
    - Headings (# / ## / ###) → <b>title</b> (Telegram has no native heading)
    - Bold **text** → <b>text</b>
    - Italic *text* / _text_ → <i>text</i>
    - Strikethrough ~~text~~ → <s>text</s>
    - Code blocks ```lang\\ncode``` → <pre><code>code</code></pre>
    - Inline code `code` → <code>code</code>
    - Links [text](url) → <a href="url">text</a>
    - Blockquotes > text → <blockquote>text</blockquote>
    - Horizontal rules (--- / ***) → stripped
    - Numbered/bullet lists → preserved as-is (plain text)
    """
    if not text:
        return text

    lines = text.split("\n")
    result_lines: List[str] = []
    in_code_block = False
    code_block_lines: List[str] = []
    code_lang = ""

    for line in lines:
        # --- Fenced code blocks (``` ... ```) ---
        if not in_code_block and line.strip().startswith("```"):
            in_code_block = True
            lang_match = re.match(r"^```(\w*)", line.strip())
            code_lang = lang_match.group(1) if lang_match else ""
            code_block_lines = []
            continue
        if in_code_block:
            if line.strip() == "```":
                in_code_block = False
                inner = escape_html("\n".join(code_block_lines))
                result_lines.append(f"<pre><code>{inner}</code></pre>")
                code_block_lines = []
                code_lang = ""
            else:
                code_block_lines.append(line)
            continue

        # --- Horizontal rules (--- / *** / ___) → strip ---
        if re.match(r"^\s*[-*_]{3,}\s*$", line):
            result_lines.append("")
            continue

        # --- Headings (# / ## / ### etc.) → bold ---
        heading = re.match(r"^(#{1,6})\s+(.*)", line)
        if heading:
            content = _format_inline(heading.group(2))
            result_lines.append(f"<b>{content}</b>")
            continue

        # --- Blockquote (> text) ---
        bq = re.match(r"^>\s?(.*)", line)
        if bq:
            content = _format_inline(bq.group(1))
            result_lines.append(f"<blockquote>{content}</blockquote>")
            continue

        # --- Regular line: apply inline formatting ---
        result_lines.append(_format_inline(line))

    # Unclosed code block — flush as pre
    if in_code_block and code_block_lines:
        inner = escape_html("\n".join(code_block_lines))
        result_lines.append(f"<pre><code>{inner}</code></pre>")

    return "\n".join(result_lines)


def _format_inline(text: str) -> str:
    """Apply inline markdown formatting to a single line of text.

    Uses a placeholder strategy so bold/italic markers can span inline-code
    segments (mirrors how the TS IR handles nested formatting):
    1. Replace inline `code` with placeholders to protect them.
    2. Escape HTML in the remaining text.
    3. Apply bold / italic / strikethrough / link transforms.
    4. Restore code placeholders as <code>...</code>.
    """
    # Step 1: stash inline code with placeholders
    code_stash: List[str] = []

    def _stash_code(m: re.Match) -> str:
        code_stash.append(m.group(1))
        return f"\x00CODE{len(code_stash) - 1}\x00"

    text = re.sub(r"`([^`\n]+)`", _stash_code, text)

    # Step 2: escape HTML entities in remaining text
    text = escape_html(text)

    # Step 3: apply inline transforms
    # Bold: **text** or __text__
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text, flags=re.DOTALL)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text, flags=re.DOTALL)
    # Italic: *text* (single asterisk, not adjacent to another *)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)
    # Italic: _text_ (not adjacent to word chars)
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"<i>\1</i>", text)
    # Strikethrough: ~~text~~
    text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)
    # Links: [text](url)
    text = re.sub(
        r"\[([^\]]+)\]\((https?://[^\)]+)\)",
        lambda m: f'<a href="{escape_html_attr(m.group(2))}">{m.group(1)}</a>',
        text,
    )

    # Step 4: restore code placeholders
    for i, code in enumerate(code_stash):
        text = text.replace(f"\x00CODE{i}\x00", f"<code>{escape_html(code)}</code>")

    return text


def chunk_message(text: str, max_length: int = 4096) -> List[str]:
    """Split long messages into chunks
    
    Telegram has a 4096 character limit per message.
    Split at paragraph boundaries when possible.
    """
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    current_chunk = ""
    
    # Split by paragraphs
    paragraphs = text.split("\n\n")
    
    for paragraph in paragraphs:
        # If adding this paragraph exceeds limit
        if len(current_chunk) + len(paragraph) + 2 > max_length:
            # If current chunk has content, save it
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
            
            # If paragraph itself is too long, split by lines or chars
            if len(paragraph) > max_length:
                lines = paragraph.split("\n")
                for line in lines:
                    if len(current_chunk) + len(line) + 1 > max_length:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                            current_chunk = ""
                        
                        # If single line is still too long, force split by chars
                        if len(line) > max_length:
                            while len(line) > max_length:
                                chunks.append(line[:max_length])
                                line = line[max_length:]
                            if line:
                                current_chunk = line
                            continue
                    current_chunk += line + "\n"
            else:
                current_chunk = paragraph + "\n\n"
        else:
            current_chunk += paragraph + "\n\n"
    
    # Add remaining chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks


def format_code_block(code: str, language: str = "") -> str:
    """Format code block for Telegram"""
    return f"<pre><code class='{language}'>{code}</code></pre>"


def format_table(rows: List[List[str]]) -> str:
    """Format table for Telegram (as monospace text)"""
    if not rows:
        return ""
    
    # Calculate column widths
    col_widths = [max(len(str(cell)) for cell in col) for col in zip(*rows)]
    
    # Build table
    lines = []
    for row in rows:
        cells = [str(cell).ljust(width) for cell, width in zip(row, col_widths)]
        lines.append(" | ".join(cells))
    
    return "<pre>" + "\n".join(lines) + "</pre>"


__all__ = [
    "markdown_to_html",
    "chunk_message",
    "format_code_block",
    "format_table",
]
