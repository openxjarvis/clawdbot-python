"""apply_patch tool — mirrors TS openclaw/src/agents/apply-patch.ts.

Uses the '*** Begin Patch' / '*** End Patch' format (not unified diff).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .base import AgentTool, ToolResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Marker constants (must exactly match TS)
# ---------------------------------------------------------------------------
BEGIN_PATCH_MARKER = "*** Begin Patch"
END_PATCH_MARKER = "*** End Patch"
ADD_FILE_MARKER = "*** Add File: "
DELETE_FILE_MARKER = "*** Delete File: "
UPDATE_FILE_MARKER = "*** Update File: "
MOVE_TO_MARKER = "*** Move to: "
EOF_MARKER = "*** End of File"
CHANGE_CONTEXT_MARKER = "@@ "
EMPTY_CHANGE_CONTEXT_MARKER = "@@"


# ---------------------------------------------------------------------------
# Data types mirroring TS
# ---------------------------------------------------------------------------

@dataclass
class AddFileHunk:
    kind: str = "add"
    path: str = ""
    contents: str = ""


@dataclass
class DeleteFileHunk:
    kind: str = "delete"
    path: str = ""


@dataclass
class UpdateFileChunk:
    change_context: str | None = None
    old_lines: list[str] = field(default_factory=list)
    new_lines: list[str] = field(default_factory=list)
    is_end_of_file: bool = False


@dataclass
class UpdateFileHunk:
    kind: str = "update"
    path: str = ""
    move_path: str | None = None
    chunks: list[UpdateFileChunk] = field(default_factory=list)


Hunk = AddFileHunk | DeleteFileHunk | UpdateFileHunk


@dataclass
class ApplyPatchSummary:
    added: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parsing — mirrors TS parsePatchText / parseOneHunk / parseUpdateFileChunk
# ---------------------------------------------------------------------------

def _check_patch_boundaries_strict(lines: list[str]) -> str | None:
    first = (lines[0].strip() if lines else "")
    last = (lines[-1].strip() if lines else "")
    if first == BEGIN_PATCH_MARKER and last == END_PATCH_MARKER:
        return None
    if first != BEGIN_PATCH_MARKER:
        return "The first line of the patch must be '*** Begin Patch'"
    return "The last line of the patch must be '*** End Patch'"


def _check_patch_boundaries_lenient(lines: list[str]) -> list[str]:
    strict_err = _check_patch_boundaries_strict(lines)
    if strict_err is None:
        return lines
    if len(lines) < 4:
        raise ValueError(strict_err)
    first, last = lines[0], lines[-1]
    # heredoc wrapping: <<EOF ... EOF
    if first in ("<<EOF", "<<'EOF'", '<<"EOF"') and last.endswith("EOF"):
        inner = lines[1:-1]
        inner_err = _check_patch_boundaries_strict(inner)
        if inner_err is None:
            return inner
        raise ValueError(inner_err)
    raise ValueError(strict_err)


def _parse_update_file_chunk(
    lines: list[str],
    line_number: int,
    allow_missing_context: bool,
) -> tuple[UpdateFileChunk, int]:
    """Parse one update chunk from lines. Returns (chunk, consumed_count)."""
    if not lines:
        raise ValueError(f"Invalid patch hunk at line {line_number}: Update hunk is empty")

    change_context: str | None = None
    start_index = 0
    if lines[0] == EMPTY_CHANGE_CONTEXT_MARKER:
        start_index = 1
    elif lines[0].startswith(CHANGE_CONTEXT_MARKER):
        change_context = lines[0][len(CHANGE_CONTEXT_MARKER):]
        start_index = 1
    elif not allow_missing_context:
        raise ValueError(
            f"Invalid patch hunk at line {line_number}: "
            f"Expected @@ context marker, got: '{lines[0]}'"
        )

    if start_index >= len(lines):
        raise ValueError(f"Invalid patch hunk at line {line_number + 1}: empty chunk")

    chunk = UpdateFileChunk(change_context=change_context)
    parsed_lines = 0

    for line in lines[start_index:]:
        if line == EOF_MARKER:
            if parsed_lines == 0:
                raise ValueError(f"Invalid patch hunk at line {line_number + 1}: empty chunk")
            chunk.is_end_of_file = True
            parsed_lines += 1
            break

        marker = line[0] if line else None

        if marker is None or line == "":
            chunk.old_lines.append("")
            chunk.new_lines.append("")
            parsed_lines += 1
            continue

        if marker == " ":
            content = line[1:]
            chunk.old_lines.append(content)
            chunk.new_lines.append(content)
            parsed_lines += 1
            continue

        if marker == "+":
            chunk.new_lines.append(line[1:])
            parsed_lines += 1
            continue

        if marker == "-":
            chunk.old_lines.append(line[1:])
            parsed_lines += 1
            continue

        if parsed_lines == 0:
            raise ValueError(
                f"Invalid patch hunk at line {line_number + 1}: "
                f"Unexpected line: '{line}'. Lines must start with ' ', '+', or '-'"
            )
        break

    return chunk, start_index + parsed_lines


def _parse_one_hunk(lines: list[str], line_number: int) -> tuple[Hunk, int]:
    """Parse one file hunk. Returns (hunk, consumed_line_count)."""
    if not lines:
        raise ValueError(f"Invalid patch hunk at line {line_number}: empty hunk")

    first_line = lines[0].strip()

    # *** Add File: <path>
    if first_line.startswith(ADD_FILE_MARKER):
        target_path = first_line[len(ADD_FILE_MARKER):]
        contents = ""
        consumed = 1
        for add_line in lines[1:]:
            if add_line.startswith("+"):
                contents += add_line[1:] + "\n"
                consumed += 1
            else:
                break
        return AddFileHunk(path=target_path, contents=contents), consumed

    # *** Delete File: <path>
    if first_line.startswith(DELETE_FILE_MARKER):
        target_path = first_line[len(DELETE_FILE_MARKER):]
        return DeleteFileHunk(path=target_path), 1

    # *** Update File: <path>
    if first_line.startswith(UPDATE_FILE_MARKER):
        target_path = first_line[len(UPDATE_FILE_MARKER):]
        remaining = lines[1:]
        consumed = 1
        move_path: str | None = None

        if remaining and remaining[0].strip().startswith(MOVE_TO_MARKER):
            move_path = remaining[0].strip()[len(MOVE_TO_MARKER):]
            remaining = remaining[1:]
            consumed += 1

        chunks: list[UpdateFileChunk] = []
        while remaining:
            if remaining[0].strip() == "":
                remaining = remaining[1:]
                consumed += 1
                continue
            if remaining[0].startswith("***"):
                break
            chunk, chunk_lines = _parse_update_file_chunk(
                remaining, line_number + consumed, len(chunks) == 0
            )
            chunks.append(chunk)
            remaining = remaining[chunk_lines:]
            consumed += chunk_lines

        if not chunks:
            raise ValueError(
                f"Invalid patch hunk at line {line_number}: "
                f"Update file hunk for '{target_path}' is empty"
            )
        return UpdateFileHunk(path=target_path, move_path=move_path, chunks=chunks), consumed

    raise ValueError(
        f"Invalid patch hunk at line {line_number}: '{lines[0]}' is not a valid hunk header. "
        f"Valid headers: '*** Add File: {{path}}', '*** Delete File: {{path}}', '*** Update File: {{path}}'"
    )


def parse_patch_text(input_text: str) -> list[Hunk]:
    """Parse patch input and return list of Hunk objects.

    Mirrors TS parsePatchText().
    """
    trimmed = input_text.strip()
    if not trimmed:
        raise ValueError("Invalid patch: input is empty.")

    lines = trimmed.splitlines()
    validated = _check_patch_boundaries_lenient(lines)
    hunks: list[Hunk] = []

    last_idx = len(validated) - 1
    remaining = validated[1:last_idx]
    line_number = 2

    while remaining:
        hunk, consumed = _parse_one_hunk(remaining, line_number)
        hunks.append(hunk)
        line_number += consumed
        remaining = remaining[consumed:]

    return hunks


# ---------------------------------------------------------------------------
# Application — mirrors TS applyPatch / applyUpdateHunk
# ---------------------------------------------------------------------------

def _seek_sequence(
    lines: list[str],
    pattern: list[str],
    start: int,
    is_end_of_file: bool,
) -> int | None:
    """Find the first occurrence of pattern starting at 'start'.

    Mirrors TS seekSequence().
    """
    if not pattern:
        return start

    if is_end_of_file:
        # Search backward from end
        for i in range(len(lines) - len(pattern), start - 1, -1):
            if lines[i:i + len(pattern)] == pattern:
                return i
        return None

    for i in range(start, len(lines) - len(pattern) + 1):
        if lines[i:i + len(pattern)] == pattern:
            return i
    return None


def _apply_update_hunk(file_path: str, chunks: list[UpdateFileChunk], cwd: str) -> str:
    """Apply update chunks to a file and return new content.

    Mirrors TS applyUpdateHunk().
    """
    abs_path = os.path.join(cwd, file_path) if not os.path.isabs(file_path) else file_path
    try:
        original_contents = Path(abs_path).read_text(encoding="utf-8")
    except Exception as exc:
        raise ValueError(f"Failed to read file {file_path}: {exc}") from exc

    original_lines = original_contents.split("\n")
    # Strip trailing empty line (consistent with TS)
    if original_lines and original_lines[-1] == "":
        original_lines.pop()

    replacements: list[tuple[int, int, list[str]]] = []
    line_index = 0

    for chunk in chunks:
        if chunk.change_context:
            ctx_idx = _seek_sequence(original_lines, [chunk.change_context], line_index, False)
            if ctx_idx is None:
                raise ValueError(
                    f"Failed to find context '{chunk.change_context}' in {file_path}"
                )
            line_index = ctx_idx + 1

        if not chunk.old_lines:
            # Pure insertion
            insert_at = (
                len(original_lines) - 1
                if original_lines and original_lines[-1] == ""
                else len(original_lines)
            )
            replacements.append((insert_at, 0, chunk.new_lines))
            continue

        pattern = chunk.old_lines
        new_slice = chunk.new_lines
        found = _seek_sequence(original_lines, pattern, line_index, chunk.is_end_of_file)

        if found is None and pattern and pattern[-1] == "":
            # Retry without trailing empty
            trimmed_pattern = pattern[:-1]
            trimmed_new = new_slice[:-1] if new_slice and new_slice[-1] == "" else new_slice
            found = _seek_sequence(original_lines, trimmed_pattern, line_index, chunk.is_end_of_file)
            if found is not None:
                pattern = trimmed_pattern
                new_slice = trimmed_new

        if found is None:
            raise ValueError(
                f"Failed to find expected lines in {file_path}:\n" + "\n".join(chunk.old_lines)
            )

        replacements.append((found, len(pattern), new_slice))
        line_index = found + len(pattern)

    # Apply replacements in reverse order to keep indices valid
    new_lines = list(original_lines)
    for start_i, length, replacement in sorted(replacements, reverse=True):
        new_lines[start_i:start_i + length] = replacement

    # Ensure trailing newline (consistent with TS)
    if not new_lines or new_lines[-1] != "":
        new_lines.append("")
    return "\n".join(new_lines)


def _format_summary(summary: ApplyPatchSummary) -> str:
    lines = ["Success. Updated the following files:"]
    for f in summary.added:
        lines.append(f"A {f}")
    for f in summary.modified:
        lines.append(f"M {f}")
    for f in summary.deleted:
        lines.append(f"D {f}")
    return "\n".join(lines)


def apply_patch(
    input_text: str,
    cwd: str,
    workspace_only: bool = True,
) -> tuple[str, ApplyPatchSummary]:
    """Apply a *** Begin Patch / *** End Patch format patch.

    Mirrors TS applyPatch().

    Returns:
        (summary_text, ApplyPatchSummary)
    """
    hunks = parse_patch_text(input_text)
    if not hunks:
        raise ValueError("No files were modified.")

    summary = ApplyPatchSummary()
    seen_added: set[str] = set()
    seen_modified: set[str] = set()
    seen_deleted: set[str] = set()

    def _record(bucket: str, display: str) -> None:
        if bucket == "added" and display not in seen_added:
            seen_added.add(display)
            summary.added.append(display)
        elif bucket == "modified" and display not in seen_modified:
            seen_modified.add(display)
            summary.modified.append(display)
        elif bucket == "deleted" and display not in seen_deleted:
            seen_deleted.add(display)
            summary.deleted.append(display)

    def _resolve_path(rel_path: str) -> str:
        abs_p = os.path.join(cwd, rel_path) if not os.path.isabs(rel_path) else rel_path
        if workspace_only:
            real_cwd = os.path.realpath(cwd)
            real_target = os.path.realpath(abs_p) if os.path.exists(abs_p) else abs_p
            # Ensure within workspace
            try:
                os.path.relpath(real_target, real_cwd)
            except ValueError:
                raise ValueError(
                    f"Patch path '{rel_path}' is outside the workspace (workspaceOnly=True)"
                )
        return abs_p

    for hunk in hunks:
        if isinstance(hunk, AddFileHunk):
            target = _resolve_path(hunk.path)
            os.makedirs(os.path.dirname(target), exist_ok=True) if os.path.dirname(target) else None
            Path(target).write_text(hunk.contents, encoding="utf-8")
            _record("added", hunk.path)
            continue

        if isinstance(hunk, DeleteFileHunk):
            target = _resolve_path(hunk.path)
            try:
                os.remove(target)
            except FileNotFoundError:
                pass  # Already gone
            _record("deleted", hunk.path)
            continue

        if isinstance(hunk, UpdateFileHunk):
            target = _resolve_path(hunk.path)
            applied = _apply_update_hunk(hunk.path, hunk.chunks, cwd)
            if hunk.move_path:
                move_target = _resolve_path(hunk.move_path)
                os.makedirs(os.path.dirname(move_target), exist_ok=True) if os.path.dirname(move_target) else None
                Path(move_target).write_text(applied, encoding="utf-8")
                try:
                    os.remove(target)
                except FileNotFoundError:
                    pass
                _record("modified", hunk.move_path)
            else:
                Path(target).write_text(applied, encoding="utf-8")
                _record("modified", hunk.path)
            continue

    return _format_summary(summary), summary


# ---------------------------------------------------------------------------
# AgentTool wrapper
# ---------------------------------------------------------------------------

class ApplyPatchTool(AgentTool):
    """Apply a *** Begin Patch / *** End Patch format patch to files.

    Mirrors TS createApplyPatchTool() from apply-patch.ts.

    The 'input' parameter must contain the full patch including '*** Begin Patch'
    and '*** End Patch' markers.
    """

    def __init__(self, cwd: str | None = None, workspace_only: bool = True):
        super().__init__()
        self.name = "apply_patch"
        self.description = (
            "Apply a patch to one or more files using the apply_patch format. "
            "The input should include *** Begin Patch and *** End Patch markers."
        )
        self._cwd = cwd or os.getcwd()
        self._workspace_only = workspace_only

    def get_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": "Patch content using the *** Begin Patch/End Patch format.",
                },
            },
            "required": ["input"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        input_text = params.get("input", "")
        if not isinstance(input_text, str):
            input_text = str(input_text)
        if not input_text.strip():
            return ToolResult(success=False, content="", error="Provide a patch input.")

        try:
            text, summary = apply_patch(input_text, self._cwd, self._workspace_only)
            return ToolResult(
                success=True,
                content=text,
                metadata={
                    "summary": {
                        "added": summary.added,
                        "modified": summary.modified,
                        "deleted": summary.deleted,
                    }
                },
            )
        except Exception as exc:
            logger.error("apply_patch failed: %s", exc, exc_info=True)
            return ToolResult(success=False, content="", error=str(exc))


__all__ = [
    "ApplyPatchTool",
    "apply_patch",
    "parse_patch_text",
    "ApplyPatchSummary",
    "AddFileHunk",
    "DeleteFileHunk",
    "UpdateFileHunk",
    "UpdateFileChunk",
    "BEGIN_PATCH_MARKER",
    "END_PATCH_MARKER",
]
