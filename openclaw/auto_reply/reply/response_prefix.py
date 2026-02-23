"""Response prefix template — interpolate {model}, {provider}, etc.

Port of TypeScript:
  openclaw/src/auto-reply/reply/response-prefix-template.ts

Supports variables like {model}, {provider}, {thinkingLevel},
{modelFull}, {identityName} in response prefix strings.
Unrecognized variables are left as-is.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Template variable pattern: {variableName} or {variable.name}
_TEMPLATE_VAR_PATTERN = re.compile(r"\{([a-zA-Z][a-zA-Z0-9.]*)\}")

# Date suffix patterns to strip from model names
_DATE_SUFFIX_RE = re.compile(r"-\d{8}$")
_LATEST_SUFFIX_RE = re.compile(r"-latest$")


@dataclass
class ResponsePrefixContext:
    """Context values for response prefix interpolation."""
    model: str | None = None             # Short model name (e.g. "gpt-5.2")
    model_full: str | None = None        # Full model ID (e.g. "openai/gpt-5.2")
    provider: str | None = None          # Provider (e.g. "anthropic")
    thinking_level: str | None = None    # e.g. "high", "low", "off"
    identity_name: str | None = None     # Agent identity name


def resolve_response_prefix_template(
    template: str | None,
    context: ResponsePrefixContext,
) -> str | None:
    """
    Interpolate template variables in a response prefix string.

    Mirrors TS resolveResponsePrefixTemplate().

    Args:
        template: Template string with {variable} placeholders
        context: Context values for interpolation

    Returns:
        Interpolated string, or None if template is None/empty.

    Example:
        resolve_response_prefix_template("[{model} | think:{thinkingLevel}]",
            ResponsePrefixContext(model="gpt-5.2", thinking_level="high"))
        # Returns: "[gpt-5.2 | think:high]"
    """
    if not template:
        return None

    def replacer(match: re.Match) -> str:
        var_name = match.group(1).lower()
        if var_name == "model":
            return context.model or match.group(0)
        if var_name == "modelfull":
            return context.model_full or match.group(0)
        if var_name == "provider":
            return context.provider or match.group(0)
        if var_name in ("thinkinglevel", "think"):
            return context.thinking_level or match.group(0)
        if var_name in ("identity.name", "identityname"):
            return context.identity_name or match.group(0)
        # Leave unrecognized variables as-is
        return match.group(0)

    return _TEMPLATE_VAR_PATTERN.sub(replacer, template)


def extract_short_model_name(full_model: str) -> str:
    """
    Extract a short model name from a full model string.

    Strips:
      - Provider prefix ("openai/" from "openai/gpt-5.2")
      - Date suffixes ("-20260205" from "claude-opus-4-6-20260205")
      - Common version suffixes ("-latest")

    Mirrors TS extractShortModelName().
    """
    slash = full_model.rfind("/")
    model_part = full_model[slash + 1:] if slash >= 0 else full_model
    model_part = _DATE_SUFFIX_RE.sub("", model_part)
    model_part = _LATEST_SUFFIX_RE.sub("", model_part)
    return model_part


def has_template_variables(template: str | None) -> bool:
    """Check if a template string contains any template variables."""
    if not template:
        return False
    return bool(_TEMPLATE_VAR_PATTERN.search(template))


def build_response_prefix_context(
    provider: str | None = None,
    model: str | None = None,
    thinking_level: str | None = None,
    identity_name: str | None = None,
) -> ResponsePrefixContext:
    """Helper to build a ResponsePrefixContext from provider/model strings."""
    model_full = f"{provider}/{model}" if (provider and model) else (model or "")
    short_model = extract_short_model_name(model or "") if model else None
    return ResponsePrefixContext(
        model=short_model,
        model_full=model_full or None,
        provider=provider,
        thinking_level=thinking_level,
        identity_name=identity_name,
    )


def apply_response_prefix(
    text: str,
    template: str | None,
    context: ResponsePrefixContext,
) -> str:
    """
    Prepend a resolved prefix to a reply text.

    Returns the original text unchanged if template is None/empty
    or if the text already starts with the resolved prefix.
    """
    if not template or not text:
        return text
    prefix = resolve_response_prefix_template(template, context)
    if not prefix:
        return text
    if text.startswith(prefix):
        return text
    return f"{prefix} {text}"
