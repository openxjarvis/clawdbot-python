"""Feishu interactive card builder.

Builds Feishu Schema 2.0 cards with ActionSet buttons for agent replies.
Mirrors the card structure used in the TypeScript extensions/feishu/src/send.ts
`buildMarkdownCard` and adds ActionSet support.

Button format (input from [[buttons:...]] directive):
    [[{"text": "Yes", "callback_data": "yes_clicked"}, ...], ...]

Feishu button `value` dict forwarded to card_action handler:
    {"text": "Yes", "callback": "yes_clicked"}

Card action handler (bot.py) receives the full value dict and dispatches
the `callback` field as the synthetic message text to the agent.

Mirrors TypeScript: extensions/feishu/src/send.ts buildMarkdownCard()
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Feishu Schema 2.0 button type values
_STYLE_MAP = {
    "default": "default",
    "primary": "primary",
    "danger": "danger",
    "success": "primary",   # map to closest equivalent
}


def build_markdown_card(text: str) -> dict[str, Any]:
    """
    Build a plain Schema 2.0 card with a single markdown element.

    Used when render_mode is 'card' or when text contains code blocks / tables.
    Mirrors TS buildMarkdownCard().
    """
    return {
        "schema": "2.0",
        "config": {"wide_screen_mode": True},
        "body": {
            "elements": [
                {"tag": "markdown", "content": text},
            ]
        },
    }


def build_button_card(
    text: str,
    buttons: list[list[dict[str, Any]]],
) -> dict[str, Any]:
    """
    Build a Schema 2.0 card with markdown content and an ActionSet.

    buttons: 2D list of button dicts. Each dict must have:
      - "text": display label
      - "callback_data": the string forwarded to the agent when clicked
      - "style" (optional): "default" | "primary" | "danger"

    The Feishu button value dict is:
      {"text": "<label>", "callback": "<callback_data>"}
    which the card_action handler uses to dispatch a synthetic message.

    All buttons in all rows are flattened into a single action element
    (Feishu ActionSet doesn't support multi-row button grids natively;
    use multiple buttons in one element for side-by-side layout).
    """
    action_buttons: list[dict[str, Any]] = []
    for row in buttons:
        for btn in row:
            label = btn.get("text", "")
            callback = btn.get("callback_data", btn.get("text", ""))
            style = _STYLE_MAP.get(btn.get("style", "default"), "default")
            if not label:
                continue
            action_buttons.append({
                "tag": "button",
                "text": {"tag": "plain_text", "content": label},
                "type": style,
                "value": {"text": label, "callback": callback},
            })

    elements: list[dict[str, Any]] = [
        {"tag": "markdown", "content": text},
    ]
    if action_buttons:
        elements.append({"tag": "hr"})
        elements.append({
            "tag": "action",
            "actions": action_buttons,
        })

    return {
        "schema": "2.0",
        "config": {"wide_screen_mode": True},
        "body": {"elements": elements},
    }


def build_card_with_disabled_buttons(
    original_card: dict[str, Any],
    selected_callback: str | None = None,
) -> dict[str, Any]:
    """
    Rebuild a card with all buttons disabled (grayed out / non-interactive).

    Called after a button is pressed to give immediate visual feedback and
    prevent double-press. The selected button is visually highlighted
    (type="primary") while others are greyed out (type="default", disabled).

    If selected_callback is provided, the matching button is kept highlighted.
    """
    import copy
    card = copy.deepcopy(original_card)
    body = card.get("body", {})
    elements = body.get("elements", [])

    for element in elements:
        if element.get("tag") != "action":
            continue
        for action in element.get("actions", []):
            if action.get("tag") != "button":
                continue
            # Mark button as disabled
            action["disabled"] = True
            # Style the selected button as primary, others as default
            btn_value = action.get("value", {})
            btn_callback = btn_value.get("callback", "")
            if selected_callback and btn_callback == selected_callback:
                action["type"] = "primary"
            else:
                action["type"] = "default"

    return card


def card_to_json_content(card: dict[str, Any]) -> str:
    """
    Serialize a card dict to the JSON content string expected by Feishu's
    im.message.create / im.message.reply API (msg_type: "interactive").

    Returns a JSON string that should be wrapped:
        {"type": "card", "data": <returned_string>}
    but the Feishu SDK often expects the card JSON directly as the content.
    """
    return json.dumps(card, ensure_ascii=False)


__all__ = [
    "build_markdown_card",
    "build_button_card",
    "build_card_with_disabled_buttons",
    "card_to_json_content",
]
