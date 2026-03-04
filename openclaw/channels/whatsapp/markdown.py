"""Markdown → WhatsApp format converter.

WhatsApp uses its own formatting:
  bold:          *text*
  italic:        _text_
  strikethrough: ~text~
  monospace:     ```text```

Standard Markdown uses:
  bold:          **text** or __text__
  italic:        *text* or _text_
  strikethrough: ~~text~~
  code:          `text` (inline) or ```text``` (block)

Mirrors TypeScript: src/markdown/whatsapp.ts
"""
from __future__ import annotations

import re

# Placeholder tokens used during conversion to protect code spans
_FENCE_PLACEHOLDER = "\x00FENCE"
_INLINE_CODE_PLACEHOLDER = "\x00CODE"


def markdown_to_whatsapp(text: str) -> str:
    """
    Convert standard Markdown bold/italic/strikethrough to WhatsApp formatting.

    Order of operations:
    1. Protect fenced code blocks (```...```) — already WhatsApp-compatible
    2. Protect inline code (`...`) — leave as-is
    3. Convert **bold** → *bold* and __bold__ → *bold*
    4. Convert ~~strike~~ → ~strike~
    5. Restore protected spans

    Italic *text* and _text_ are left alone since WhatsApp uses _text_ for italic
    and single * is already WhatsApp bold — no conversion needed for single markers.
    """
    if not text:
        return text

    # 1. Extract and protect fenced code blocks
    fences: list[str] = []

    def protect_fence(m: re.Match) -> str:
        fences.append(m.group(0))
        return f"{_FENCE_PLACEHOLDER}{len(fences) - 1}"

    result = re.sub(r"```[\s\S]*?```", protect_fence, text)

    # 2. Extract and protect inline code
    inline_codes: list[str] = []

    def protect_inline(m: re.Match) -> str:
        inline_codes.append(m.group(0))
        return f"{_INLINE_CODE_PLACEHOLDER}{len(inline_codes) - 1}"

    result = re.sub(r"`[^`\n]+`", protect_inline, result)

    # 3. Convert **bold** → *bold* and __bold__ → *bold*
    # Must handle **text** before *text* to avoid partial matches
    result = re.sub(r"\*\*(.+?)\*\*", r"*\1*", result, flags=re.DOTALL)
    result = re.sub(r"__(.+?)__", r"*\1*", result, flags=re.DOTALL)

    # 4. Convert ~~strike~~ → ~strike~
    result = re.sub(r"~~(.+?)~~", r"~\1~", result, flags=re.DOTALL)

    # 5. Restore protected spans (in reverse order to avoid index collisions)
    for i in range(len(inline_codes) - 1, -1, -1):
        result = result.replace(f"{_INLINE_CODE_PLACEHOLDER}{i}", inline_codes[i])
    for i in range(len(fences) - 1, -1, -1):
        result = result.replace(f"{_FENCE_PLACEHOLDER}{i}", fences[i])

    return result


def convert_markdown_tables(text: str, table_mode: str = "native") -> str:
    """
    Convert Markdown tables based on the configured mode.

    Modes:
    - "native" (default): leave tables as-is (WhatsApp doesn't render them anyway)
    - "ascii":  convert to ASCII box-drawing style
    - "simple": strip table formatting to plain pipe-separated lines
    """
    if table_mode == "native" or not _has_markdown_table(text):
        return text

    if table_mode == "simple":
        return _strip_table_formatting(text)

    if table_mode == "ascii":
        return _convert_table_to_ascii(text)

    return text


def _has_markdown_table(text: str) -> bool:
    return bool(re.search(r"^\|.+\|$", text, re.MULTILINE))


def _strip_table_formatting(text: str) -> str:
    """Strip table separators, keep content lines."""
    lines = text.split("\n")
    result_lines: list[str] = []
    for line in lines:
        # Skip separator rows like |---|---|
        if re.match(r"^\|[\s\-:]+\|[\s\-:|]*$", line):
            continue
        result_lines.append(line)
    return "\n".join(result_lines)


def _convert_table_to_ascii(text: str) -> str:
    """Convert Markdown table to a simple formatted text representation."""
    # Find table blocks
    def replace_table(block: str) -> str:
        rows = [r for r in block.split("\n") if r.strip()]
        if len(rows) < 2:
            return block

        # Parse cells
        parsed: list[list[str]] = []
        for row in rows:
            # Skip separator rows
            if re.match(r"^\|[\s\-:]+\|[\s\-:|]*$", row):
                continue
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            parsed.append(cells)

        if not parsed:
            return block

        # Compute column widths
        col_count = max(len(r) for r in parsed)
        widths = [0] * col_count
        for row in parsed:
            for i, cell in enumerate(row):
                if i < col_count:
                    widths[i] = max(widths[i], len(cell))

        def fmt_row(cells: list[str]) -> str:
            padded = [
                cells[i].ljust(widths[i]) if i < len(cells) else " " * widths[i]
                for i in range(col_count)
            ]
            return "| " + " | ".join(padded) + " |"

        def sep_row() -> str:
            return "|-" + "-|-".join("-" * w for w in widths) + "-|"

        lines = [fmt_row(parsed[0]), sep_row()]
        for row in parsed[1:]:
            lines.append(fmt_row(row))
        return "\n".join(lines)

    # Replace each table block
    table_pattern = re.compile(r"(?:^\|.+\|$\n?)+", re.MULTILINE)
    return table_pattern.sub(lambda m: replace_table(m.group(0)), text)
