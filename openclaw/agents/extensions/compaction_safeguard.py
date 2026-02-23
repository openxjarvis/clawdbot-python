"""
Compaction safeguard extension — aligned with TypeScript
openclaw/src/agents/pi-extensions/compaction-safeguard.ts.

Enriches compaction summaries with:
- Tool failures that occurred in the session
- File operations (read / modified files)
- Critical workspace rules from AGENTS.md
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

MAX_TOOL_FAILURES = 8
MAX_TOOL_FAILURE_CHARS = 240
MAX_SUMMARY_CONTEXT_CHARS = 2_000

FALLBACK_SUMMARY = (
    "Summary unavailable due to context limits. Older messages were truncated."
)
TURN_PREFIX_INSTRUCTIONS = (
    "This summary covers the prefix of a split turn. "
    "Focus on the original request, early progress, "
    "and any details needed to understand the retained suffix."
)


# ---------------------------------------------------------------------------
# Tool failure helpers
# ---------------------------------------------------------------------------

def _normalize_failure_text(text: str) -> str:
    import re
    return re.sub(r"\s+", " ", text).strip()


def _truncate_failure_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 3)] + "..."


def _format_tool_failure_meta(details: Any) -> str | None:
    if not details or not isinstance(details, dict):
        return None
    parts: list[str] = []
    if isinstance(details.get("status"), str):
        parts.append(f"status={details['status']}")
    exit_code = details.get("exitCode")
    if isinstance(exit_code, (int, float)) and exit_code == exit_code and abs(exit_code) != float("inf"):
        parts.append(f"exitCode={int(exit_code)}")
    return " ".join(parts) if parts else None


def _extract_tool_result_text(content: Any) -> str:
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
            parts.append(block["text"])
    return "\n".join(parts)


def collect_tool_failures(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collect tool failures from a message list — mirrors TS collectToolFailures()."""
    failures: list[dict[str, Any]] = []
    seen: set[str] = set()

    for message in messages:
        if not isinstance(message, dict):
            continue
        if message.get("role") != "toolResult":
            continue
        if message.get("isError") is not True:
            continue
        tool_call_id = message.get("toolCallId", "")
        if not isinstance(tool_call_id, str) or not tool_call_id:
            continue
        if tool_call_id in seen:
            continue
        seen.add(tool_call_id)

        tool_name = message.get("toolName", "tool")
        if not isinstance(tool_name, str) or not tool_name.strip():
            tool_name = "tool"
        raw_text = _extract_tool_result_text(message.get("content"))
        meta = _format_tool_failure_meta(message.get("details"))
        normalized = _normalize_failure_text(raw_text)
        summary = _truncate_failure_text(
            normalized or ("failed" if meta else "failed (no output)"),
            MAX_TOOL_FAILURE_CHARS,
        )
        failures.append({"toolCallId": tool_call_id, "toolName": tool_name, "summary": summary, "meta": meta})

    return failures


def format_tool_failures_section(failures: list[dict[str, Any]]) -> str:
    """Format tool failures into a markdown section."""
    if not failures:
        return ""
    lines: list[str] = []
    for failure in failures[:MAX_TOOL_FAILURES]:
        meta_str = f" ({failure['meta']})" if failure.get("meta") else ""
        lines.append(f"- {failure['toolName']}{meta_str}: {failure['summary']}")
    if len(failures) > MAX_TOOL_FAILURES:
        lines.append(f"- ...and {len(failures) - MAX_TOOL_FAILURES} more")
    return "\n\n## Tool Failures\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# File operation helpers
# ---------------------------------------------------------------------------

def compute_file_lists(
    file_ops: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """Split file ops into read-only and modified lists.

    Mirrors TS computeFileLists().
    """
    edited: set[str] = set(file_ops.get("edited", []))
    written: set[str] = set(file_ops.get("written", []))
    read: set[str] = set(file_ops.get("read", []))
    modified = edited | written
    read_files = sorted(f for f in read if f not in modified)
    modified_files = sorted(modified)
    return read_files, modified_files


def format_file_operations(read_files: list[str], modified_files: list[str]) -> str:
    """Format file operations into XML-like sections."""
    sections: list[str] = []
    if read_files:
        sections.append(f"<read-files>\n{chr(10).join(read_files)}\n</read-files>")
    if modified_files:
        sections.append(f"<modified-files>\n{chr(10).join(modified_files)}\n</modified-files>")
    return ("\n\n" + "\n\n".join(sections)) if sections else ""


# ---------------------------------------------------------------------------
# Workspace context (AGENTS.md)
# ---------------------------------------------------------------------------

def _extract_sections(content: str, section_names: list[str]) -> list[str]:
    """Extract named markdown sections from content.

    Mirrors TS extractSections() from post-compaction-context.ts.
    """
    import re
    result: list[str] = []
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        heading_match = re.match(r"^(#{1,3})\s+(.+)$", line)
        if heading_match:
            level_hashes = heading_match.group(1)
            heading_text = heading_match.group(2).strip()
            if any(name.lower() in heading_text.lower() for name in section_names):
                section_lines = [line]
                level = len(level_hashes)
                i += 1
                while i < len(lines):
                    next_line = lines[i]
                    next_match = re.match(r"^(#{1,3})\s+", next_line)
                    if next_match and len(next_match.group(1)) <= level:
                        break
                    section_lines.append(next_line)
                    i += 1
                result.append("\n".join(section_lines))
                continue
        i += 1
    return result


def read_workspace_context_for_summary(workspace_dir: str | None = None) -> str:
    """Read critical workspace rules from AGENTS.md.

    Mirrors TS readWorkspaceContextForSummary().
    """
    workspace_dir = workspace_dir or os.getcwd()
    agents_path = Path(workspace_dir) / "AGENTS.md"
    if not agents_path.exists():
        return ""
    try:
        content = agents_path.read_text(encoding="utf-8")
        sections = _extract_sections(content, ["Session Startup", "Red Lines"])
        if not sections:
            return ""
        combined = "\n\n".join(sections)
        if len(combined) > MAX_SUMMARY_CONTEXT_CHARS:
            combined = combined[:MAX_SUMMARY_CONTEXT_CHARS] + "\n...[truncated]..."
        return f"\n\n<workspace-critical-rules>\n{combined}\n</workspace-critical-rules>"
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Compaction safeguard entry points
# ---------------------------------------------------------------------------

def build_fallback_summary(
    messages_to_summarize: list[dict[str, Any]],
    turn_prefix_messages: list[dict[str, Any]],
    file_ops: dict[str, Any] | None = None,
) -> tuple[str, list[str], list[str]]:
    """Build a fallback summary (no LLM) enriched with tool failures and file ops.

    Returns (summary_text, read_files, modified_files).
    """
    all_messages = list(messages_to_summarize) + list(turn_prefix_messages)
    tool_failures = collect_tool_failures(all_messages)
    tool_failure_section = format_tool_failures_section(tool_failures)

    read_files: list[str] = []
    modified_files: list[str] = []
    file_ops_summary = ""
    if file_ops:
        read_files, modified_files = compute_file_lists(file_ops)
        file_ops_summary = format_file_operations(read_files, modified_files)

    summary = f"{FALLBACK_SUMMARY}{tool_failure_section}{file_ops_summary}"
    return summary, read_files, modified_files


def enrich_compaction_summary(
    base_summary: str,
    *,
    messages_to_summarize: list[dict[str, Any]],
    turn_prefix_messages: list[dict[str, Any]],
    file_ops: dict[str, Any] | None = None,
    workspace_dir: str | None = None,
    include_workspace_context: bool = True,
) -> str:
    """Enrich an existing compaction summary with tool failures and file ops.

    This is the Python entry point used by PiAgentRuntime's compaction hook.
    """
    all_messages = list(messages_to_summarize) + list(turn_prefix_messages)
    tool_failures = collect_tool_failures(all_messages)
    tool_failure_section = format_tool_failures_section(tool_failures)

    file_ops_summary = ""
    if file_ops:
        read_files, modified_files = compute_file_lists(file_ops)
        file_ops_summary = format_file_operations(read_files, modified_files)

    workspace_context = ""
    if include_workspace_context:
        workspace_context = read_workspace_context_for_summary(workspace_dir)

    return f"{base_summary}{tool_failure_section}{file_ops_summary}{workspace_context}"


def apply_compaction_safeguard(
    event: dict[str, Any],
    workspace_dir: str | None = None,
) -> dict[str, Any]:
    """Apply compaction safeguard to a session_before_compact event.

    This function is the Python equivalent of the TS extension's on("session_before_compact")
    handler. It can be called by PiAgentRuntime when compaction is triggered.

    Args:
        event: Compaction event dict with:
            - preparation: dict with messagesToSummarize, turnPrefixMessages, fileOps, etc.
            - customInstructions: str | None
        workspace_dir: Optional workspace directory for AGENTS.md lookup.

    Returns:
        Enriched compaction result dict.
    """
    preparation = event.get("preparation", {})
    messages_to_summarize: list[dict[str, Any]] = preparation.get("messagesToSummarize", [])
    turn_prefix_messages: list[dict[str, Any]] = preparation.get("turnPrefixMessages", [])
    file_ops: dict[str, Any] | None = preparation.get("fileOps")
    first_kept_entry_id = preparation.get("firstKeptEntryId")
    tokens_before = preparation.get("tokensBefore")

    fallback_summary, read_files, modified_files = build_fallback_summary(
        messages_to_summarize,
        turn_prefix_messages,
        file_ops,
    )

    workspace_context = read_workspace_context_for_summary(workspace_dir)
    if workspace_context:
        fallback_summary = fallback_summary + workspace_context

    return {
        "compaction": {
            "summary": fallback_summary,
            "firstKeptEntryId": first_kept_entry_id,
            "tokensBefore": tokens_before,
            "details": {"readFiles": read_files, "modifiedFiles": modified_files},
        }
    }
