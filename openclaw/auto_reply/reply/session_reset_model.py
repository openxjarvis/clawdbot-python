"""Session reset model override — mirrors TypeScript src/auto-reply/reply/session-reset-model.ts

Parses the body after a reset command for an optional model token:
  /new gpt-4o              → single fuzzy token
  /new openai gpt-4o       → provider/model two-token
  /new openai/gpt-4o       → explicit composite

If a recognized model is found, applies it to the session entry and
returns the cleaned body (model tokens stripped).
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _split_body(body: str) -> dict:
    tokens = [t for t in body.split() if t]
    return {
        "tokens": tokens,
        "first": tokens[0] if tokens else None,
        "second": tokens[1] if len(tokens) > 1 else None,
    }


async def apply_reset_model_override(
    *,
    cfg: Any,
    reset_triggered: bool,
    body_stripped: str | None,
    session_key: str | None = None,
    store_path: str | None = None,
    default_provider: str | None = None,
    default_model: str | None = None,
) -> dict[str, Any]:
    """Parse and apply an optional model override from the post-reset body.

    Mirrors TS applyResetModelOverride() in session-reset-model.ts.

    Returns {
        "selection": ModelOverrideSelection | None,
        "cleaned_body": str | None,
    }
    """
    if not reset_triggered:
        return {}
    raw_body = (body_stripped or "").strip()
    if not raw_body:
        return {}

    split = _split_body(raw_body)
    first = split["first"]
    second = split["second"]
    tokens = split["tokens"]
    if not first:
        return {}

    try:
        from openclaw.agents.model_catalog import load_model_catalog
        from openclaw.agents.model_selection import (
            build_allowed_model_set,
            normalize_provider_id,
            model_key,
            build_model_alias_index,
            resolve_model_ref_from_string,
            DEFAULT_PROVIDER,
        )
        from openclaw.agents.sessions.model_overrides import (
            ModelOverrideSelection,
            apply_model_override_to_session_entry,
        )
    except ImportError as exc:
        logger.debug("apply_reset_model_override: import error: %s", exc)
        return {}

    effective_default_provider = default_provider or DEFAULT_PROVIDER
    effective_default_model = default_model or ""

    try:
        catalog = await load_model_catalog(config=cfg)
    except Exception as exc:
        logger.debug("apply_reset_model_override: catalog load failed: %s", exc)
        return {}

    allowed = build_allowed_model_set(
        cfg,
        catalog,
        default_provider=effective_default_provider,
        default_model=effective_default_model,
    )
    allowed_keys: set[str] = allowed.get("allowed_keys", set())
    if not allowed_keys:
        return {}

    # Build set of known providers from allowed keys
    providers: set[str] = set()
    for key in allowed_keys:
        slash = key.find("/")
        if slash > 0:
            providers.add(normalize_provider_id(key[:slash]))

    alias_index = build_model_alias_index(cfg, effective_default_provider)

    def _resolve(raw: str) -> "ModelOverrideSelection | None":
        # resolve_model_ref_from_string returns {"ref": ModelRef, "alias": ...} or None
        resolved = resolve_model_ref_from_string(raw, effective_default_provider, alias_index)
        if not resolved:
            return None
        ref = resolved.get("ref") if isinstance(resolved, dict) else resolved
        if not ref:
            return None
        key = model_key(ref.provider, ref.model)
        if allowed_keys and key not in allowed_keys:
            return None
        is_default = (
            ref.provider == effective_default_provider
            and ref.model == effective_default_model
        )
        return ModelOverrideSelection(
            provider=ref.provider,
            model=ref.model,
            is_default=is_default,
        )

    selection: "ModelOverrideSelection | None" = None
    consumed = 0

    # Try provider/model two-token first: "openai gpt-4o"
    if first and second and normalize_provider_id(first) in providers:
        composite = f"{normalize_provider_id(first)}/{second}"
        sel = _resolve(composite)
        if sel:
            selection = sel
            consumed = 2

    # Try explicit single token: "openai/gpt-4o" or "gpt-4o"
    if not selection:
        sel = _resolve(first)
        if sel:
            selection = sel
            consumed = 1

    # Try fuzzy single token (len >= 6 or known provider)
    if not selection:
        allow_fuzzy = normalize_provider_id(first) in providers or len(first.strip()) >= 6
        if allow_fuzzy:
            sel = _resolve(first)
            if sel:
                selection = sel
                consumed = 1

    if not selection:
        return {}

    cleaned_body = " ".join(tokens[consumed:]).strip()

    # Apply to session entry if we have a session_key + store_path
    if session_key and store_path:
        try:
            from openclaw.config.sessions.store_utils import (
                load_session_store_from_path,
                save_session_store_to_path,
            )
            store = load_session_store_from_path(store_path)
            key_lower = session_key.lower()
            entry = store.get(key_lower) or store.get(session_key)
            if entry is not None:
                apply_model_override_to_session_entry(entry, selection)
                store[key_lower] = entry
                save_session_store_to_path(store_path, store)
        except Exception as exc:
            logger.debug("apply_reset_model_override: store update failed: %s", exc)

    return {
        "selection": selection,
        "cleaned_body": cleaned_body,
    }


__all__ = ["apply_reset_model_override"]
