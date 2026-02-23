"""
Session key resolution from various identifiers.

Fully aligned with TypeScript openclaw/src/gateway/sessions-resolve.ts.
Supports resolving sessions by direct key, sessionId, or label, including
legacy key migration and result limits.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Limit how many results we load before reporting ambiguity (mirrors TS)
_SESSION_ID_SEARCH_LIMIT = 8
_LABEL_SEARCH_LIMIT = 2


# ---------------------------------------------------------------------------
# Label parsing (mirrors TS parseSessionLabel)
# ---------------------------------------------------------------------------

def _parse_session_label(raw: Any) -> dict[str, Any]:
    """Return {"ok": True, "label": str} or {"ok": False, "error": str}."""
    if raw is None:
        return {"ok": False, "error": "invalid label: null"}
    label = str(raw).strip()
    if not label:
        return {"ok": False, "error": "invalid label: empty"}
    if len(label) > 64:
        return {"ok": False, "error": f"label must be ≤64 characters (got {len(label)})"}
    if not re.match(r'^[a-zA-Z0-9_\-\.]+$', label):
        return {"ok": False, "error": "invalid label: use a-z, 0-9, -, _, ."}
    return {"ok": True, "label": label}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_combined_store(cfg: Any) -> tuple[str, dict[str, Any]]:
    """Load a combined session store from all configured agents."""
    try:
        from openclaw.config.sessions.store import load_session_store
        from openclaw.config.sessions.paths import get_default_store_path
        from openclaw.routing.session_key import normalize_agent_id

        agents_section = (cfg or {}).get("agents") or {}
        agents_list = agents_section.get("agents") or agents_section.get("list") or []
        agent_ids = [
            normalize_agent_id(str(e["id"]))
            for e in agents_list
            if isinstance(e, dict) and e.get("id")
        ]
        if not agent_ids:
            agent_ids = ["main"]

        combined: dict[str, Any] = {}
        store_path = "(multiple)"
        for agent_id in agent_ids:
            sp = str(get_default_store_path(agent_id))
            store_path = sp
            try:
                store = load_session_store(sp)
                for k, v in store.items():
                    if k not in combined:
                        combined[k] = v
                    else:
                        # Keep the entry with the latest updatedAt
                        existing_ts = (
                            combined[k].get("updatedAt") if isinstance(combined[k], dict)
                            else getattr(combined[k], "updatedAt", 0)
                        ) or 0
                        new_ts = (
                            v.get("updatedAt") if isinstance(v, dict)
                            else getattr(v, "updatedAt", 0)
                        ) or 0
                        if new_ts > existing_ts:
                            combined[k] = v
            except Exception:
                pass
        return store_path, combined
    except Exception:
        return "(unknown)", {}


def _resolve_store_target(cfg: Any, key: str) -> dict[str, Any]:
    """Thin wrapper around resolve_gateway_session_store_target."""
    try:
        from openclaw.gateway.session_utils import resolve_gateway_session_store_target
        t = resolve_gateway_session_store_target(key, "main")
        return {
            "store_path": t.store_path,
            "canonical_key": t.canonical_key,
            "store_keys": t.store_keys,
            "agent_id": t.agent_id,
        }
    except Exception:
        return {
            "store_path": "",
            "canonical_key": key,
            "store_keys": [key],
            "agent_id": "main",
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_session_key_from_resolve_params(
    p: dict[str, Any],
    cfg: Any = None,
) -> dict[str, Any]:
    """
    Resolve session key from one of: key, sessionId, or label.
    Mirrors TS resolveSessionKeyFromResolveParams().

    Returns {"ok": True, "key": str} or {"ok": False, "error": {"code": ..., "message": ...}}.
    """
    def _err(msg: str) -> dict[str, Any]:
        return {"ok": False, "error": {"code": "INVALID_REQUEST", "message": msg}}

    key = str(p.get("key") or "").strip()
    session_id = str(p.get("sessionId") or "").strip()
    label_raw = p.get("label")
    has_label = isinstance(label_raw, str) and label_raw.strip()

    selection_count = sum([bool(key), bool(session_id), bool(has_label)])
    if selection_count > 1:
        return _err("Provide either key, sessionId, or label (not multiple)")
    if selection_count == 0:
        return _err("Either key, sessionId, or label is required")

    # -----------------------------------------------------------------
    # 1. Resolve by key — with legacy key migration
    # -----------------------------------------------------------------
    if key:
        try:
            from openclaw.config.sessions.store import load_session_store
            from openclaw.config.sessions.store_utils import update_session_store_with_mutator
            from openclaw.gateway.session_utils import (
                find_store_keys_ignore_case,
                prune_legacy_store_keys,
                resolve_gateway_session_store_target,
            )

            target = resolve_gateway_session_store_target(key, "main")
            store_path = target.store_path
            canonical_key = target.canonical_key
            store_keys = target.store_keys

            store = load_session_store(store_path)
            store_dict: dict[str, Any] = (
                dict(store) if not isinstance(store, dict) else store
            )

            if canonical_key in store_dict:
                return {"ok": True, "key": canonical_key}

            # Find legacy key
            legacy_key: str | None = None
            for candidate in store_keys:
                if candidate in store_dict:
                    legacy_key = candidate
                    break

            if legacy_key is None:
                return _err(f"No session found: {key}")

            # Migrate legacy → canonical
            def _migrate(s: dict[str, Any]) -> None:
                if canonical_key not in s and legacy_key in s:
                    s[canonical_key] = s[legacy_key]
                prune_legacy_store_keys(
                    store=s,
                    canonical_key=canonical_key,
                    candidates=store_keys,
                )

            try:
                update_session_store_with_mutator(store_path, _migrate)
            except Exception as mig_exc:
                logger.warning("Legacy key migration failed: %s", mig_exc)

            return {"ok": True, "key": canonical_key}

        except Exception as exc:
            logger.error("Failed to resolve session by key '%s': %s", key, exc)
            return _err(str(exc))

    # -----------------------------------------------------------------
    # 2. Resolve by sessionId — capped at SESSION_ID_SEARCH_LIMIT
    # -----------------------------------------------------------------
    if session_id:
        store_path, store = _load_combined_store(cfg)
        matches = [
            k for k, entry in store.items()
            if (
                (entry.get("sessionId") if isinstance(entry, dict) else getattr(entry, "sessionId", None))
                == session_id
                or k == session_id
            )
        ]
        # Apply limit before reporting ambiguity (mirrors TS limit: 8)
        limited = matches[:_SESSION_ID_SEARCH_LIMIT]
        if len(limited) == 0:
            return _err(f"No session found: {session_id}")
        if len(limited) > 1 or len(matches) > 1:
            keys_str = ", ".join(limited)
            return _err(f"Multiple sessions found for sessionId: {session_id} ({keys_str})")
        return {"ok": True, "key": limited[0]}

    # -----------------------------------------------------------------
    # 3. Resolve by label — validate first, cap at LABEL_SEARCH_LIMIT
    # -----------------------------------------------------------------
    parsed_label = _parse_session_label(label_raw)
    if not parsed_label["ok"]:
        return _err(parsed_label["error"])

    label = parsed_label["label"]
    store_path, store = _load_combined_store(cfg)

    matches = [
        k for k, entry in store.items()
        if (
            entry.get("label") if isinstance(entry, dict) else getattr(entry, "label", None)
        ) == label
    ]
    limited = matches[:_LABEL_SEARCH_LIMIT]
    if len(limited) == 0:
        return _err(f"No session found with label: {label}")
    if len(limited) > 1 or len(matches) > 1:
        keys_str = ", ".join(limited)
        return _err(f"Multiple sessions found with label: {label} ({keys_str})")
    return {"ok": True, "key": limited[0]}
