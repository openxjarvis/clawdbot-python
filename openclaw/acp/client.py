"""ACP client — mirrors src/acp/client.ts

Provides:
- create_acp_client(): spawn an ACP server subprocess and connect via NDJSON
- resolve_permission_request(): auto-approve safe tools, interactive prompt for dangerous
- run_acp_client_interactive(): readline REPL for manual interaction
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import uuid
from typing import Any, Callable

# Tools that are safe to auto-approve without user prompt
_SAFE_AUTO_APPROVE_TOOL_IDS = frozenset(["read", "search", "web_search", "memory_search"])
_TRUSTED_SAFE_TOOL_ALIASES = frozenset(["search"])
_READ_TOOL_PATH_KEYS = ["path", "file_path", "filePath"]
_TOOL_NAME_MAX_LENGTH = 128
_TOOL_NAME_PATTERN = re.compile(r"^[a-z0-9._-]+$")

# Tools that always require an interactive prompt, even if otherwise safe
_DANGEROUS_ACP_TOOLS: frozenset[str] = frozenset([
    "shell", "exec", "bash", "run_command", "execute", "write",
    "delete", "rm", "create_file", "overwrite",
])

_TOOL_KIND_BY_ID: dict[str, str] = {
    "read": "read",
    "search": "search",
    "web_search": "search",
    "memory_search": "search",
}


# ---------------------------------------------------------------------------
# Permission resolution helpers
# ---------------------------------------------------------------------------

def _as_record(value: Any) -> dict | None:
    if isinstance(value, dict):
        return value
    return None


def _read_first_string(source: dict | None, keys: list[str]) -> str | None:
    if not source:
        return None
    for key in keys:
        val = source.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _normalize_tool_name(value: str) -> str | None:
    normalized = value.strip().lower()
    if not normalized or len(normalized) > _TOOL_NAME_MAX_LENGTH:
        return None
    if not _TOOL_NAME_PATTERN.match(normalized):
        return None
    return normalized


def _parse_tool_name_from_title(title: str | None) -> str | None:
    if not title:
        return None
    head = title.split(":", 1)[0].strip()
    return _normalize_tool_name(head) if head else None


def _resolve_tool_kind(tool_name: str | None) -> str | None:
    if not tool_name:
        return None
    return _TOOL_KIND_BY_ID.get(tool_name, "other")


def _resolve_tool_name_for_permission(params: dict) -> str | None:
    tool_call = params.get("toolCall") or {}
    tool_meta = _as_record(tool_call.get("_meta"))
    raw_input = _as_record(tool_call.get("rawInput"))
    from_meta = _read_first_string(tool_meta, ["toolName", "tool_name", "name"])
    from_raw = _read_first_string(raw_input, ["tool", "toolName", "tool_name", "name"])
    from_title = _parse_tool_name_from_title(tool_call.get("title"))
    return _normalize_tool_name(from_meta or from_raw or from_title or "")


def _extract_path_from_tool_title(tool_title: str | None, tool_name: str | None) -> str | None:
    if not tool_title:
        return None
    sep = tool_title.find(":")
    if sep < 0:
        return None
    tail = tool_title[sep + 1:].strip()
    if not tail:
        return None
    keyed = re.search(r"(?:^|,\s*)(?:path|file_path|filePath)\s*:\s*([^,]+)", tail)
    if keyed:
        return keyed.group(1).strip()
    if tool_name == "read":
        return tail
    return None


def _resolve_tool_path_candidate(params: dict, tool_name: str | None, tool_title: str | None) -> str | None:
    raw_input = _as_record((params.get("toolCall") or {}).get("rawInput"))
    from_raw = _read_first_string(raw_input, _READ_TOOL_PATH_KEYS)
    from_title = _extract_path_from_tool_title(tool_title, tool_name)
    return from_raw or from_title


def _resolve_absolute_scoped_path(value: str, cwd: str) -> str | None:
    candidate = value.strip()
    if not candidate:
        return None
    if candidate.startswith("file://"):
        try:
            from urllib.parse import unquote
            from urllib.parse import urlparse
            parsed = urlparse(candidate)
            candidate = unquote(parsed.path)
        except Exception:
            return None
    if candidate == "~":
        candidate = os.path.expanduser("~")
    elif candidate.startswith("~/"):
        candidate = os.path.join(os.path.expanduser("~"), candidate[2:])
    abs_path = candidate if os.path.isabs(candidate) else os.path.normpath(os.path.join(cwd, candidate))
    return abs_path


def _is_path_within_root(candidate: str, root: str) -> bool:
    rel = os.path.relpath(candidate, root)
    return rel == "." or (not rel.startswith("..") and not os.path.isabs(rel))


def _is_read_tool_scoped_to_cwd(params: dict, tool_name: str | None, tool_title: str | None, cwd: str) -> bool:
    if tool_name != "read":
        return False
    raw_path = _resolve_tool_path_candidate(params, tool_name, tool_title)
    if not raw_path:
        return False
    abs_path = _resolve_absolute_scoped_path(raw_path, cwd)
    if not abs_path:
        return False
    return _is_path_within_root(abs_path, os.path.realpath(cwd))


def _should_auto_approve(params: dict, tool_name: str | None, tool_title: str | None, cwd: str) -> bool:
    if not tool_name or tool_name not in _SAFE_AUTO_APPROVE_TOOL_IDS:
        return False
    if tool_name == "read":
        return _is_read_tool_scoped_to_cwd(params, tool_name, tool_title, cwd)
    return True


def _pick_option(options: list[dict], kinds: list[str]) -> dict | None:
    for kind in kinds:
        for opt in options:
            if opt.get("kind") == kind:
                return opt
    return None


async def _prompt_user_permission(tool_name: str | None, tool_title: str | None = None) -> bool:
    """Interactively ask the user via stderr/stdin."""
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        print(f"[permission denied] {tool_name or 'unknown'}: non-interactive terminal", file=sys.stderr)
        return False

    label = (
        f"{tool_title} ({tool_name})" if tool_title and tool_name
        else tool_title or tool_name or "unknown tool"
    )
    loop = asyncio.get_running_loop()

    def _ask() -> bool:
        try:
            answer = input(f'\n[permission] Allow "{label}"? (y/N) ')
            approved = answer.strip().lower() == "y"
            print(f"[permission {'approved' if approved else 'denied'}] {tool_name or 'unknown'}", file=sys.stderr)
            return approved
        except (EOFError, KeyboardInterrupt):
            return False

    return await loop.run_in_executor(None, _ask)


async def resolve_permission_request(
    params: dict,
    *,
    cwd: str | None = None,
    prompt: Callable | None = None,
    log: Callable[[str], None] | None = None,
) -> dict:
    """
    Resolve a permission request from an ACP tool call.

    - Auto-approves safe, read-only tools scoped to the working directory.
    - Prompts the user interactively for dangerous or unknown tools.
    - Always prompts for tools in _DANGEROUS_ACP_TOOLS.

    Returns a RequestPermissionResponse dict:
      {"outcome": {"outcome": "selected", "optionId": "..."}}
      or {"outcome": {"outcome": "cancelled"}}
    """
    _log = log or (lambda line: print(line, file=sys.stderr))
    _prompt = prompt or _prompt_user_permission
    _cwd = cwd or os.getcwd()

    options: list[dict] = params.get("options") or []
    tool_call = params.get("toolCall") or {}
    tool_title = tool_call.get("title") or "tool"
    tool_name = _resolve_tool_name_for_permission(params)
    tool_kind = _resolve_tool_kind(tool_name)

    if not options:
        _log(f"[permission cancelled] {tool_name or 'unknown'}: no options available")
        return {"outcome": {"outcome": "cancelled"}}

    allow_option = _pick_option(options, ["allow_once", "allow_always"])
    reject_option = _pick_option(options, ["reject_once", "reject_always"])

    is_dangerous = tool_name and tool_name in _DANGEROUS_ACP_TOOLS
    auto_approve = _should_auto_approve(params, tool_name, tool_title, _cwd) and not is_dangerous

    if auto_approve:
        option = allow_option or options[0]
        _log(f"[permission auto-approved] {tool_name} ({tool_kind or 'unknown'})")
        return {"outcome": {"outcome": "selected", "optionId": option["optionId"]}}

    _log(f'\n[permission requested] {tool_title}{f" ({tool_name})" if tool_name else ""}{f" [{tool_kind}]" if tool_kind else ""}')
    approved = await _prompt(tool_name, tool_title)

    if approved and allow_option:
        return {"outcome": {"outcome": "selected", "optionId": allow_option["optionId"]}}
    if not approved and reject_option:
        return {"outcome": {"outcome": "selected", "optionId": reject_option["optionId"]}}

    _log(f"[permission cancelled] {tool_name or 'unknown'}: missing {'allow' if approved else 'reject'} option")
    return {"outcome": {"outcome": "cancelled"}}


# ---------------------------------------------------------------------------
# ACP client connection — NDJSON over subprocess stdin/stdout
# ---------------------------------------------------------------------------

class AcpClientHandle:
    """
    Handle to a spawned ACP server process with an open NDJSON connection.

    Provides send() / receive() for the NDJSON request/response protocol,
    along with initialized session_id from the newSession handshake.
    """

    def __init__(
        self,
        proc: asyncio.subprocess.Process,
        session_id: str,
        cwd: str,
        verbose: bool = False,
    ) -> None:
        self._proc = proc
        self.session_id = session_id
        self.cwd = cwd
        self._verbose = verbose
        self._req_lock = asyncio.Lock()
        self._pending: dict[str, asyncio.Future] = {}
        self._reader_task: asyncio.Task | None = None

    def start_reader(self) -> None:
        self._reader_task = asyncio.ensure_future(self._read_loop())

    def _log(self, msg: str) -> None:
        if self._verbose:
            print(f"[acp-client] {msg}", file=sys.stderr)

    async def _read_loop(self) -> None:
        assert self._proc.stdout
        while True:
            line_bytes = await self._proc.stdout.readline()
            if not line_bytes:
                break
            line = line_bytes.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(msg, dict):
                continue

            # Session update notification (no id) — print to stdout
            if msg.get("type") == "sessionUpdate":
                _print_session_update(msg)
                continue

            req_id = msg.get("id")
            if req_id and req_id in self._pending:
                fut = self._pending.pop(req_id)
                if not fut.done():
                    err = msg.get("error")
                    if err:
                        fut.set_exception(Exception(err.get("message", "ACP error") if isinstance(err, dict) else str(err)))
                    else:
                        fut.set_result(msg.get("result"))

    async def send_request(self, method: str, params: Any = None) -> Any:
        req_id = str(uuid.uuid4())
        frame: dict[str, Any] = {"id": req_id, "method": method}
        if params is not None:
            frame["params"] = params

        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        self._pending[req_id] = future

        assert self._proc.stdin
        async with self._req_lock:
            line = json.dumps(frame) + "\n"
            self._proc.stdin.write(line.encode())
            await self._proc.stdin.drain()

        self._log(f"→ {method}")
        return await future

    async def prompt(self, text: str) -> dict:
        return await self.send_request("prompt", {
            "sessionId": self.session_id,
            "prompt": [{"type": "text", "text": text}],
        })

    async def cancel(self) -> None:
        await self.send_request("cancel", {"sessionId": self.session_id})

    def kill(self) -> None:
        try:
            self._proc.kill()
        except Exception:
            pass


def _print_session_update(msg: dict) -> None:
    update = msg.get("update") or {}
    tag = update.get("sessionUpdate")
    if tag == "agent_message_chunk":
        content = update.get("content") or {}
        if content.get("type") == "text":
            sys.stdout.write(content.get("text", ""))
            sys.stdout.flush()
    elif tag == "tool_call":
        title = update.get("title", "")
        status = update.get("status", "")
        print(f"\n[tool] {title} ({status})")
    elif tag == "tool_call_update":
        tool_id = update.get("toolCallId", "")
        status = update.get("status", "")
        if status:
            print(f"[tool update] {tool_id}: {status}")
    elif tag == "available_commands_update":
        cmds = update.get("availableCommands") or []
        names = " ".join(f"/{c.get('name', '')}" for c in cmds if c.get("name"))
        if names:
            print(f"\n[commands] {names}")


async def create_acp_client(
    *,
    cwd: str | None = None,
    server_command: str | None = None,
    server_args: list[str] | None = None,
    server_verbose: bool = False,
    verbose: bool = False,
) -> AcpClientHandle:
    """
    Spawn an ACP server subprocess and initialize the connection.

    The server is launched with stdin/stdout pipes for NDJSON communication.
    Returns an AcpClientHandle with an active sessionId after the initialize
    + newSession handshake.
    """
    _cwd = cwd or os.getcwd()
    log = (lambda m: print(f"[acp-client] {m}", file=sys.stderr)) if verbose else (lambda m: None)

    cmd_parts: list[str]
    if server_command:
        cmd_parts = [server_command] + (server_args or [])
    else:
        python = sys.executable
        pkg_main = _resolve_acp_server_entry()
        args = ["acp"] + (server_args or [])
        if server_verbose and "--verbose" not in args and "-v" not in args:
            args.append("--verbose")
        if pkg_main:
            cmd_parts = [python, pkg_main] + args
        else:
            cmd_parts = [python, "-m", "openclaw.acp.server"] + args

    log(f"spawning: {' '.join(cmd_parts)}")

    env = {**os.environ, "OPENCLAW_SHELL": "acp-client"}
    proc = await asyncio.create_subprocess_exec(
        *cmd_parts,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=None,
        cwd=_cwd,
        env=env,
    )

    handle = AcpClientHandle(proc, session_id="", cwd=_cwd, verbose=verbose)
    handle.start_reader()

    log("initializing")
    await handle.send_request("initialize", {
        "protocolVersion": "1.0",
        "clientCapabilities": {
            "fs": {"readTextFile": True, "writeTextFile": True},
            "terminal": True,
        },
        "clientInfo": {"name": "openclaw-acp-client", "version": "1.0.0"},
    })

    log("creating session")
    session_result = await handle.send_request("newSession", {
        "cwd": _cwd,
        "mcpServers": [],
    })

    session_id = (session_result or {}).get("sessionId", "")
    handle.session_id = session_id
    return handle


def _resolve_acp_server_entry() -> str | None:
    """Try to find the openclaw server entry point for direct invocation."""
    try:
        import openclaw
        pkg_dir = os.path.dirname(openclaw.__file__)
        candidate = os.path.join(pkg_dir, "acp", "server.py")
        if os.path.exists(candidate):
            return candidate
    except Exception:
        pass
    return None


async def run_acp_client_interactive(
    *,
    cwd: str | None = None,
    server_command: str | None = None,
    server_args: list[str] | None = None,
    server_verbose: bool = False,
    verbose: bool = False,
) -> None:
    """
    Start an interactive ACP client REPL.

    Reads prompts from stdin, sends them to the ACP server, and prints
    responses to stdout.  Type 'exit' or 'quit' to stop.
    """
    handle = await create_acp_client(
        cwd=cwd,
        server_command=server_command,
        server_args=server_args,
        server_verbose=server_verbose,
        verbose=verbose,
    )

    print("OpenClaw ACP client")
    print(f"Session: {handle.session_id}")
    print('Type a prompt, or "exit" to quit.\n')

    loop = asyncio.get_running_loop()

    while True:
        try:
            text = await loop.run_in_executor(None, lambda: input("> "))
        except (EOFError, KeyboardInterrupt):
            break

        text = text.strip()
        if not text:
            continue
        if text in ("exit", "quit"):
            break

        try:
            response = await handle.prompt(text)
            stop_reason = (response or {}).get("stopReason", "unknown")
            print(f"\n[{stop_reason}]\n")
        except Exception as exc:
            print(f"\n[error] {exc}\n")

    handle.kill()
    print("\nACP client stopped.")
