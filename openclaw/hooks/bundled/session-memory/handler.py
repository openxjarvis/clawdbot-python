"""Session memory hook handler.

Saves session context to memory when /new command is triggered.
Creates a new dated memory file with LLM-generated slug.

Aligned with TypeScript openclaw/src/hooks/bundled/session-memory/handler.ts
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


async def get_recent_session_content(
    session_file_path: str,
    message_count: int = 15
) -> str | None:
    """Read recent messages from session file for slug generation.
    
    Args:
        session_file_path: Path to session JSONL file
        message_count: Number of messages to include
    
    Returns:
        Recent conversation content or None if unavailable
    """
    try:
        with open(session_file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        lines = content.strip().split("\n")
        
        # Parse JSONL and extract user/assistant messages
        all_messages: list[str] = []
        for line in lines:
            try:
                entry = json.loads(line)
                # Session files have entries with type="message" containing a nested message object
                if entry.get("type") == "message" and entry.get("message"):
                    msg = entry["message"]
                    role = msg.get("role")
                    if role in ("user", "assistant") and msg.get("content"):
                        # Skip inter-session user messages (if we have provenance info)
                        if role == "user" and msg.get("_provenance", {}).get("source") == "inter_session":
                            continue
                        
                        # Extract text content
                        content_data = msg["content"]
                        if isinstance(content_data, list):
                            # Find text content block
                            text = next(
                                (c.get("text") for c in content_data if c.get("type") == "text"),
                                None
                            )
                        else:
                            text = content_data
                        
                        if text and not text.startswith("/"):
                            all_messages.append(f"{role}: {text}")
            except (json.JSONDecodeError, KeyError, TypeError):
                # Skip invalid JSON lines
                continue
        
        # Slice to get exactly message_count messages
        recent_messages = all_messages[-message_count:]
        return "\n".join(recent_messages) if recent_messages else None
    except Exception as err:
        logger.debug(f"Failed to read session content: {err}")
        return None


async def get_recent_session_content_with_reset_fallback(
    session_file_path: str,
    message_count: int = 15
) -> str | None:
    """Try the active transcript first; if /new already rotated it, fallback to the latest .jsonl.reset.* sibling.
    
    Args:
        session_file_path: Path to session file
        message_count: Number of messages to include
    
    Returns:
        Recent conversation content or None
    """
    primary = await get_recent_session_content(session_file_path, message_count)
    if primary:
        return primary
    
    try:
        session_path = Path(session_file_path)
        dir_path = session_path.parent
        base_name = session_path.name
        reset_prefix = f"{base_name}.reset."
        
        # Find reset files
        reset_candidates = sorted(
            [f.name for f in dir_path.iterdir() if f.name.startswith(reset_prefix)]
        )
        
        if not reset_candidates:
            return primary
        
        # Use the latest reset file
        latest_reset_path = dir_path / reset_candidates[-1]
        fallback = await get_recent_session_content(str(latest_reset_path), message_count)
        
        if fallback:
            logger.debug(
                f"Loaded session content from reset fallback: {session_file_path} -> {latest_reset_path}"
            )
        
        return fallback or primary
    except Exception as err:
        logger.debug(f"Failed to load reset fallback: {err}")
        return primary


async def find_previous_session_file(
    sessions_dir: str,
    current_session_file: str | None,
    session_id: str | None
) -> str | None:
    """Find previous session file based on session ID or current file.
    
    Args:
        sessions_dir: Directory containing session files
        current_session_file: Current session file path
        session_id: Session ID
    
    Returns:
        Path to previous session file or None
    """
    try:
        sessions_path = Path(sessions_dir)
        if not sessions_path.exists():
            return None
        
        # Remove .reset. suffix if present
        def strip_reset_suffix(filename: str) -> str:
            reset_index = filename.find(".reset.")
            return filename[:reset_index] if reset_index != -1 else filename
        
        # Try to find by stripped filename
        if current_session_file:
            base_from_reset = strip_reset_suffix(Path(current_session_file).name)
            candidate = sessions_path / base_from_reset
            if candidate.exists():
                return str(candidate)
        
        # Try to find by session ID
        if session_id:
            session_id = session_id.strip()
            canonical_file = sessions_path / f"{session_id}.jsonl"
            if canonical_file.exists():
                return str(canonical_file)
            
            # Try topic variants
            topic_variants = sorted(
                [
                    f for f in sessions_path.glob(f"{session_id}-topic-*.jsonl")
                    if ".reset." not in f.name
                ],
                reverse=True
            )
            if topic_variants:
                return str(topic_variants[0])
        
        # Fallback: find most recent non-reset jsonl file
        if not current_session_file:
            return None
        
        non_reset_jsonl = sorted(
            [f for f in sessions_path.glob("*.jsonl") if ".reset." not in f.name],
            reverse=True
        )
        if non_reset_jsonl:
            return str(non_reset_jsonl[0])
    except Exception as err:
        logger.debug(f"Failed to find previous session file: {err}")
    
    return None


def resolve_hook_config_simple(cfg: dict[str, Any] | None, hook_name: str) -> dict[str, Any] | None:
    """Simple hook config resolver (placeholder until config.py is implemented).
    
    Args:
        cfg: OpenClaw configuration
        hook_name: Name of the hook
    
    Returns:
        Hook-specific configuration or None
    """
    if not cfg:
        return None
    
    hooks_config = cfg.get("hooks", {})
    internal_config = hooks_config.get("internal", {})
    entries = internal_config.get("entries", {})
    return entries.get(hook_name)


async def save_session_to_memory(event: Any) -> None:
    """Save session context to memory when /new command is triggered.
    
    Args:
        event: The hook event
    """
    # Only trigger on 'new' command
    if event.type != "command" or event.action != "new":
        return
    
    try:
        logger.debug("Hook triggered for /new command")
        
        context = event.context or {}
        cfg = context.get("cfg")
        
        # Resolve workspace directory
        # TODO: Import proper agent scope resolution
        workspace_dir = os.path.expanduser("~/.openclaw/workspace")
        if cfg and cfg.get("workspace", {}).get("dir"):
            workspace_dir = cfg["workspace"]["dir"]
        
        memory_dir = Path(workspace_dir) / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        
        # Get today's date for filename
        now = event.timestamp
        date_str = now.strftime("%Y-%m-%d")
        
        # Generate descriptive slug from session using LLM
        # Prefer previousSessionEntry (old session before /new) over current (which may be empty)
        session_entry = context.get("previousSessionEntry") or context.get("sessionEntry") or {}
        current_session_id = session_entry.get("sessionId") or session_entry.get("session_id")
        current_session_file = session_entry.get("sessionFile") or session_entry.get("session_file")
        
        # If sessionFile is empty or looks like a new/reset file, try to find the previous session file
        if not current_session_file or ".reset." in current_session_file:
            sessions_dirs = set()
            if current_session_file:
                sessions_dirs.add(str(Path(current_session_file).parent))
            sessions_dirs.add(str(Path(workspace_dir) / "sessions"))
            
            for sessions_dir in sessions_dirs:
                recovered_file = await find_previous_session_file(
                    sessions_dir,
                    current_session_file,
                    current_session_id
                )
                if recovered_file:
                    current_session_file = recovered_file
                    logger.debug(f"Found previous session file: {current_session_file}")
                    break
        
        logger.debug(
            f"Session context resolved: sessionId={current_session_id}, "
            f"sessionFile={current_session_file}, hasCfg={bool(cfg)}"
        )
        
        # Read message count from hook config (default: 15)
        hook_config = resolve_hook_config_simple(cfg, "session-memory")
        message_count = 15
        if hook_config and isinstance(hook_config.get("messages"), int):
            if hook_config["messages"] > 0:
                message_count = hook_config["messages"]
        
        slug: str | None = None
        session_content: str | None = None
        
        if current_session_file:
            # Get recent conversation content, with fallback to rotated reset transcript
            session_content = await get_recent_session_content_with_reset_fallback(
                current_session_file,
                message_count
            )
            logger.debug(
                f"Session content loaded: length={len(session_content) if session_content else 0}, "
                f"messageCount={message_count}"
            )
            
            # Avoid calling the model provider in unit tests
            is_test_env = (
                os.getenv("OPENCLAW_TEST_FAST") == "1" or
                os.getenv("PYTEST_CURRENT_TEST") is not None or
                os.getenv("NODE_ENV") == "test"
            )
            allow_llm_slug = not is_test_env and (not hook_config or hook_config.get("llmSlug") != False)
            
            if session_content and cfg and allow_llm_slug:
                logger.debug("Calling generateSlugViaLLM...")
                # Use LLM to generate a descriptive slug
                try:
                    from openclaw.hooks.llm_slug_generator import generate_slug_via_llm
                    slug = await generate_slug_via_llm(session_content=session_content, cfg=cfg)
                    logger.debug(f"Generated slug: {slug}")
                except (ImportError, Exception) as err:
                    logger.debug(f"LLM slug generation failed or unavailable: {err}")
        
        # If no slug, use timestamp
        if not slug:
            time_slug = now.strftime("%H%M%S").replace(":", "")
            slug = time_slug[:4]  # HHMM
            logger.debug(f"Using fallback timestamp slug: {slug}")
        
        # Create filename with date and slug
        filename = f"{date_str}-{slug}.md"
        memory_file_path = memory_dir / filename
        logger.debug(f"Memory file path resolved: {filename}")
        
        # Format time as HH:MM:SS UTC
        time_str = now.strftime("%H:%M:%S")
        
        # Extract context details
        session_id = session_entry.get("sessionId") or session_entry.get("session_id") or "unknown"
        source = context.get("commandSource") or context.get("command_source") or "unknown"
        
        # Build Markdown entry
        entry_parts = [
            f"# Session: {date_str} {time_str} UTC",
            "",
            f"- **Session Key**: {event.session_key}",
            f"- **Session ID**: {session_id}",
            f"- **Source**: {source}",
            "",
        ]
        
        # Include conversation content if available
        if session_content:
            entry_parts.extend([
                "## Conversation Summary",
                "",
                session_content,
                "",
            ])
        
        entry = "\n".join(entry_parts)
        
        # Write to new memory file
        memory_file_path.write_text(entry, encoding="utf-8")
        logger.debug("Memory file written successfully")
        
        # Log completion
        rel_path = str(memory_file_path).replace(os.path.expanduser("~"), "~")
        logger.info(f"Session context saved to {rel_path}")
    except Exception as err:
        logger.error(f"Failed to save session memory: {err}", exc_info=True)


# Default export (matches TS pattern)
default = save_session_to_memory
