"""Gateway boot runner — runs BOOT.md via agent command on gateway startup.

Mirrors TypeScript openclaw/src/gateway/boot.ts exactly:
- Loads BOOT.md from workspace
- Builds a boot prompt with SILENT_REPLY_TOKEN instructions
- Runs the agent command (snapshots+restores main session mapping)
- Returns a typed BootRunResult

The boot-md bundled hook calls run_boot_once() on gateway:startup events.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

logger = logging.getLogger(__name__)

BOOT_FILENAME = "BOOT.md"
SILENT_REPLY_TOKEN = "NO_REPLY"


# ---------------------------------------------------------------------------
# Result type — mirrors TS BootRunResult union
# ---------------------------------------------------------------------------

@dataclass
class BootRunResult:
    status: Literal["skipped", "ran", "failed"]
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def generate_boot_session_id() -> str:
    """Generate a unique boot session ID.

    Format: boot-{ISO-timestamp-sanitized}-{uuid8}
    Mirrors TS generateBootSessionId().
    """
    now = datetime.now(timezone.utc)
    ts = now.isoformat().replace(":", "-").replace(".", "-").replace("+00:00", "").replace("T", "_")
    suffix = str(uuid.uuid4())[:8]
    return f"boot-{ts}-{suffix}"


def build_boot_prompt(content: str) -> str:
    """Build the boot prompt injected as the user message.

    Mirrors TS buildBootPrompt() exactly — same wording.
    """
    return "\n".join([
        "You are running a boot check. Follow BOOT.md instructions exactly.",
        "",
        "BOOT.md:",
        content,
        "",
        "If BOOT.md asks you to send a message, use the message tool (action=send with channel + target).",
        "Use the `target` field (not `to`) for message tool destinations.",
        f"After sending with the message tool, reply with ONLY: {SILENT_REPLY_TOKEN}.",
        f"If nothing needs attention, reply with ONLY: {SILENT_REPLY_TOKEN}.",
    ])


def _load_boot_file(workspace_dir: Path) -> dict:
    """Load BOOT.md from workspace synchronously.

    Returns dict with keys: status (ok/missing/empty), content (optional).
    """
    boot_path = workspace_dir / BOOT_FILENAME
    try:
        content = boot_path.read_text(encoding="utf-8")
        trimmed = content.strip()
        if not trimmed:
            return {"status": "empty"}
        return {"status": "ok", "content": trimmed}
    except FileNotFoundError:
        return {"status": "missing"}
    except Exception as exc:
        raise exc


# ---------------------------------------------------------------------------
# Session mapping snapshot/restore — mirrors TS snapshotMainSessionMapping /
# restoreMainSessionMapping.  Uses the Python session store utilities.
# ---------------------------------------------------------------------------

def _snapshot_main_session_mapping(cfg: Any, session_key: str) -> dict:
    """Snapshot the current main session store entry so we can restore it.

    The boot runner uses a temporary session ID. Without the snapshot we would
    overwrite the main session entry with the boot session, breaking the user's
    ongoing conversation.

    Mirrors TS snapshotMainSessionMapping().
    """
    from openclaw.routing.session_key import resolve_agent_id_from_session_key
    from openclaw.config.sessions.paths import resolve_store_path

    try:
        agent_id = resolve_agent_id_from_session_key(session_key)
        session_cfg = cfg.get("session", {}) if isinstance(cfg, dict) else {}
        store_path = str(resolve_store_path(
            session_cfg.get("store"),
            agent_id=agent_id,
        ))

        from openclaw.config.sessions.store import load_session_store
        store = load_session_store(store_path)
        entry = store.get(session_key)

        return {
            "store_path": store_path,
            "session_key": session_key,
            "can_restore": True,
            "had_entry": entry is not None,
            "entry": dict(entry) if entry else None,
        }
    except Exception as exc:
        logger.debug("boot: could not snapshot main session mapping: %s", exc)
        return {
            "store_path": None,
            "session_key": session_key,
            "can_restore": False,
            "had_entry": False,
            "entry": None,
        }


def _restore_main_session_mapping(snapshot: dict) -> Optional[str]:
    """Restore the main session mapping after boot finishes.

    Mirrors TS restoreMainSessionMapping().
    Returns an error string on failure, None on success.
    """
    if not snapshot.get("can_restore"):
        return None
    try:
        from openclaw.config.sessions.store import load_session_store, update_session_store

        store_path = snapshot["store_path"]
        session_key = snapshot["session_key"]

        if snapshot["had_entry"] and snapshot["entry"]:
            update_session_store(session_key, snapshot["entry"])
        else:
            # Remove the entry the boot session may have created
            store = load_session_store(store_path)
            if hasattr(store, "delete"):
                store.delete(session_key)
        return None
    except Exception as exc:
        return str(exc)


# ---------------------------------------------------------------------------
# Main entry point — called by boot-md hook handler
# ---------------------------------------------------------------------------

async def run_boot_once(
    *,
    cfg: Any,
    workspace_dir: str | Path,
    deps: Any = None,
) -> BootRunResult:
    """Run BOOT.md via agent command on gateway startup.

    Mirrors TS runBootOnce() from gateway/boot.ts:
    1. Load BOOT.md — skip if missing or empty.
    2. Build the boot prompt string.
    3. Snapshot the current main session mapping.
    4. Run the agent command (dispatches to PiAgentRuntime).
    5. Restore the main session mapping.

    Args:
        cfg:           Loaded OpenClaw config dict.
        workspace_dir: Agent workspace directory path.
        deps:          Optional CLI deps (not used in Python, kept for API parity).

    Returns:
        BootRunResult with status "skipped", "ran", or "failed".
    """
    workspace_path = Path(workspace_dir) if isinstance(workspace_dir, str) else workspace_dir

    # Step 1 — load BOOT.md
    try:
        result = _load_boot_file(workspace_path)
    except Exception as exc:
        message = str(exc)
        logger.error("boot: failed to read %s: %s", BOOT_FILENAME, message)
        return BootRunResult(status="failed", reason=message)

    if result["status"] in ("missing", "empty"):
        logger.debug("boot: BOOT.md %s — skipping", result["status"])
        return BootRunResult(status="skipped", reason=result["status"])

    # Step 2 — resolve session key and build prompt
    from openclaw.agents.agent_scope import resolve_default_agent_id
    from openclaw.routing.session_key import build_agent_main_session_key

    agent_id = resolve_default_agent_id(cfg) if cfg else "main"
    session_key = build_agent_main_session_key(agent_id)
    session_id = generate_boot_session_id()
    boot_prompt = build_boot_prompt(result["content"])

    # Step 3 — snapshot session mapping
    mapping_snapshot = _snapshot_main_session_mapping(cfg, session_key)

    # Step 4 — run agent command
    agent_failure: Optional[str] = None
    try:
        await _run_boot_agent_command(
            cfg=cfg,
            session_key=session_key,
            session_id=session_id,
            message=boot_prompt,
        )
        logger.info("boot: BOOT.md executed successfully (session_id=%s)", session_id)
    except Exception as exc:
        agent_failure = str(exc)
        # Log as debug instead of error - this is expected during early bootstrap
        # The boot-md hook will retry on gateway:startup event
        logger.debug("boot: agent run failed (will retry): %s", agent_failure)

    # Step 5 — restore session mapping
    restore_failure = _restore_main_session_mapping(mapping_snapshot)
    if restore_failure:
        logger.error("boot: failed to restore main session mapping: %s", restore_failure)

    if not agent_failure and not restore_failure:
        return BootRunResult(status="ran")

    reason_parts = [
        f"agent run failed: {agent_failure}" if agent_failure else None,
        f"mapping restore failed: {restore_failure}" if restore_failure else None,
    ]
    return BootRunResult(
        status="failed",
        reason="; ".join(p for p in reason_parts if p),
    )


async def _run_boot_agent_command(
    *,
    cfg: Any,
    session_key: str,
    session_id: str,
    message: str,
) -> None:
    """Dispatch a headless agent turn for the boot check.

    Uses the globally registered agent runtime and session/tool managers from
    the gateway handlers module. If the runtime is not yet available this will
    raise, which the caller catches.
    """
    from openclaw.gateway import handlers as _handlers

    agent_runtime = _handlers._agent_runtime
    session_manager = _handlers._session_manager
    tool_registry = _handlers._tool_registry

    if not agent_runtime:
        raise RuntimeError("Agent runtime not available — cannot run BOOT.md")
    if not session_manager:
        raise RuntimeError("Session manager not available — cannot run BOOT.md")

    # Get or create session
    session = session_manager.get_session(session_id)
    tools = tool_registry.list_tools() if tool_registry else []

    # Run the turn, consuming all events silently (deliver=False equivalent)
    async for event in agent_runtime.run_turn(session, message, tools):
        evt_type = getattr(event, "type", "")
        if evt_type == "error":
            data = getattr(event, "data", {})
            error_msg = data.get("message", str(event)) if isinstance(data, dict) else str(event)
            logger.warning("boot: agent event error: %s", error_msg)
        # All other events are silently consumed — no delivery to any channel
