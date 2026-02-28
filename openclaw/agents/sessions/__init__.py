"""Session-level overrides and policies."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Session store helpers — mirrors TS updateSessionStoreEntry / loadSessionEntry
# ---------------------------------------------------------------------------

def _resolve_sessions_store_path(cfg: Any) -> Path | None:
    """Resolve the sessions.json path from config."""
    try:
        if isinstance(cfg, dict):
            # Try agents.defaults.stateDir or ~/.openclaw
            import os
            state_dir = (
                cfg.get("gateway", {}).get("stateDir")
                or cfg.get("stateDir")
                or os.path.expanduser("~/.openclaw")
            )
            agent_id = (
                (cfg.get("agents") or {}).get("defaults", {}).get("agentId")
                or "main"
            )
            return Path(state_dir) / "agents" / agent_id / "sessions" / "sessions.json"
    except Exception:
        pass
    return None


def _load_sessions_json(store_path: Path) -> dict[str, Any]:
    """Load a sessions.json store file."""
    if not store_path.exists():
        return {}
    try:
        return json.loads(store_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_sessions_json(store_path: Path, store: dict[str, Any]) -> None:
    """Save a sessions.json store file."""
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")


def load_session_entry(session_key: str, cfg: Any = None) -> dict[str, Any] | None:
    """Load a single session entry from the sessions.json store.

    Mirrors TS loadSessionStore + store[sessionKey] lookup.

    Args:
        session_key: Session key to load.
        cfg: Optional config dict used to resolve the store path.

    Returns:
        Session entry dict or None if not found.
    """
    if not session_key:
        return None
    store_path = _resolve_sessions_store_path(cfg)
    if not store_path:
        return None
    store = _load_sessions_json(store_path)
    return store.get(session_key) or store.get(session_key.lower())


def patch_session_entry(
    session_key: str,
    patch: dict[str, Any],
    cfg: Any = None,
) -> dict[str, Any] | None:
    """Apply a partial patch to a session entry and persist it.

    Mirrors TS updateSessionStoreEntry() — reads, merges, writes.

    Args:
        session_key: Session key to update.
        patch: Fields to update (None values are skipped).
        cfg: Optional config dict used to resolve the store path.

    Returns:
        Updated session entry, or None if session doesn't exist.
    """
    if not session_key or not patch:
        return None
    store_path = _resolve_sessions_store_path(cfg)
    if not store_path:
        logger.debug("patch_session_entry: cannot resolve store path")
        return None
    try:
        store = _load_sessions_json(store_path)
        existing = store.get(session_key) or store.get(session_key.lower()) or {}
        # Merge: filter out None values so they don't overwrite existing
        merged = {**existing}
        for k, v in patch.items():
            if v is not None:
                merged[k] = v
            elif k in merged and v is None:
                # Explicit None means unset
                del merged[k]
        merged["updatedAt"] = int(time.time() * 1000)
        canonical = session_key.lower() if session_key.lower() in store else session_key
        store[canonical] = merged
        _save_sessions_json(store_path, store)
        return merged
    except Exception as exc:
        logger.warning(f"patch_session_entry({session_key}): {exc}")
        return None


from .input_provenance import (
    INPUT_PROVENANCE_KIND_VALUES,
    InputProvenance,
    InputProvenanceKind,
    apply_input_provenance_to_user_message,
    has_inter_session_user_provenance,
    is_inter_session_input_provenance,
    normalize_input_provenance,
)
from .level_overrides import (
    VERBOSE_LEVEL_CLEAR,
    VerboseLevel,
    apply_verbose_override,
    normalize_verbose_level,
    parse_verbose_override,
)
from .model_overrides import (
    ModelOverrideSelection,
    apply_model_override_to_session_entry,
)
from .send_policy import (
    SessionSendPolicyDecision,
    normalize_send_policy,
    resolve_send_policy,
)
from .session_label import SESSION_LABEL_MAX_LENGTH, parse_session_label
from .transcript_events import (
    SessionTranscriptListener,
    emit_session_transcript_update,
    on_session_transcript_update,
)

__all__ = [
    # session store helpers
    "load_session_entry",
    "patch_session_entry",
    # input_provenance
    "INPUT_PROVENANCE_KIND_VALUES",
    "InputProvenanceKind",
    "InputProvenance",
    "normalize_input_provenance",
    "apply_input_provenance_to_user_message",
    "is_inter_session_input_provenance",
    "has_inter_session_user_provenance",
    # level_overrides
    "VerboseLevel",
    "normalize_verbose_level",
    "parse_verbose_override",
    "apply_verbose_override",
    "VERBOSE_LEVEL_CLEAR",
    # model_overrides
    "ModelOverrideSelection",
    "apply_model_override_to_session_entry",
    # send_policy
    "SessionSendPolicyDecision",
    "normalize_send_policy",
    "resolve_send_policy",
    # session_label
    "SESSION_LABEL_MAX_LENGTH",
    "parse_session_label",
    # transcript_events
    "SessionTranscriptListener",
    "on_session_transcript_update",
    "emit_session_transcript_update",
]
