"""Inline directive tag parsing.

Parses [[reply_to:ID]], [[silent]], [[buttons:...]], etc.
Aligned with TypeScript src/utils/directive-tags.ts

Button directive format:
  [[buttons:Label1=data1|Label2=data2]]            # one row, two buttons
  [[buttons:Label1=data1|Label2=data2;Label3=data3]]  # two rows (;-separated)

Each button is Label=callback_data. The parsed result is a 2D list:
  [[{"text": "Label1", "callback_data": "data1"}, ...], ...]
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class DirectiveParseResult:
    """Result of parsing inline directives."""
    
    text: str  # Text with directives removed
    has_reply_tag: bool = False
    reply_to_id: Optional[str] = None
    reply_to_explicit_id: Optional[str] = None
    reply_to_current: bool = False
    is_silent: bool = False
    # Inline buttons parsed from [[buttons:...]] directive.
    # Format: list of rows, each row is a list of button dicts.
    # Each dict has "text" (display label) and "callback_data" (payload).
    buttons: Optional[list[list[dict]]] = None


def parse_inline_directives(
    text: str,
    strip_audio_tag: bool = False,
    strip_reply_tags: bool = True
) -> DirectiveParseResult:
    """Parse inline directive tags from text.
    
    Supports:
    - [[reply_to:MESSAGE_ID]] - Reply to specific message
    - [[reply_to_current]] - Reply to current message
    - [[silent]] - Silent reply (don't send)
    
    Args:
        text: Text to parse
        strip_audio_tag: Whether to strip audio tags
        strip_reply_tags: Whether to strip reply tags
    
    Returns:
        DirectiveParseResult with parsed directives and cleaned text
    """
    if not text:
        return DirectiveParseResult(text="")
    
    has_reply_tag = False
    reply_to_id: Optional[str] = None
    reply_to_explicit_id: Optional[str] = None
    reply_to_current = False
    is_silent = False
    clean_text = text
    
    # Check for [[silent]] directive
    silent_pattern = r'\[\[silent\]\]'
    if re.search(silent_pattern, clean_text, re.IGNORECASE):
        is_silent = True
        clean_text = re.sub(silent_pattern, '', clean_text, flags=re.IGNORECASE)
    
    # Check for [[reply_to_current]] directive
    current_pattern = r'\[\[reply_to_current\]\]'
    if re.search(current_pattern, clean_text, re.IGNORECASE):
        has_reply_tag = True
        reply_to_current = True
        if strip_reply_tags:
            clean_text = re.sub(current_pattern, '', clean_text, flags=re.IGNORECASE)
    
    # Check for [[reply_to:ID]] directive
    reply_to_pattern = r'\[\[reply_to:([^\]]+)\]\]'
    match = re.search(reply_to_pattern, clean_text, re.IGNORECASE)
    if match:
        has_reply_tag = True
        msg_id = match.group(1).strip()
        reply_to_explicit_id = msg_id
        reply_to_id = msg_id
        if strip_reply_tags:
            clean_text = re.sub(reply_to_pattern, '', clean_text, flags=re.IGNORECASE)

    # Check for [[buttons:...]] directive
    # Format: [[buttons:Label1=data1|Label2=data2;Label3=data3]]
    # ';' separates rows, '|' separates buttons within a row, '=' separates label from data.
    buttons: Optional[list[list[dict]]] = None
    buttons_pattern = r'\[\[buttons:([^\]]*)\]\]'
    buttons_match = re.search(buttons_pattern, clean_text, re.IGNORECASE)
    if buttons_match:
        buttons_spec = buttons_match.group(1).strip()
        parsed_rows: list[list[dict]] = []
        for row_spec in buttons_spec.split(";"):
            row_spec = row_spec.strip()
            if not row_spec:
                continue
            row_buttons: list[dict] = []
            for btn_spec in row_spec.split("|"):
                btn_spec = btn_spec.strip()
                if not btn_spec:
                    continue
                if "=" in btn_spec:
                    label, _, callback_data = btn_spec.partition("=")
                    label = label.strip()
                    callback_data = callback_data.strip()
                else:
                    label = btn_spec
                    callback_data = btn_spec
                if label:
                    row_buttons.append({"text": label, "callback_data": callback_data})
            if row_buttons:
                parsed_rows.append(row_buttons)
        if parsed_rows:
            buttons = parsed_rows
        clean_text = re.sub(buttons_pattern, '', clean_text, flags=re.IGNORECASE)

    # Clean up extra whitespace while preserving newlines for MEDIA: token parsing
    # CRITICAL: Do NOT replace newlines - split_media_from_output needs line structure
    clean_text = re.sub(r'[ \t]+', ' ', clean_text)  # Compress spaces/tabs only
    clean_text = re.sub(r'\n{3,}', '\n\n', clean_text)  # Max 2 consecutive newlines
    clean_text = clean_text.strip()
    
    return DirectiveParseResult(
        text=clean_text,
        has_reply_tag=has_reply_tag,
        reply_to_id=reply_to_id,
        reply_to_explicit_id=reply_to_explicit_id,
        reply_to_current=reply_to_current,
        is_silent=is_silent,
        buttons=buttons,
    )
