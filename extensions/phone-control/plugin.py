"""phone-control extension — arm/disarm high-risk phone node commands.

Mirrors TypeScript: openclaw/extensions/phone-control/index.ts
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any

STATE_VERSION = 2
STATE_REL_PATH = ("plugins", "phone-control", "armed.json")

GROUP_COMMANDS: dict[str, list[str]] = {
    "camera": ["camera.snap", "camera.clip"],
    "screen": ["screen.record"],
    "writes": ["calendar.add", "contacts.add", "reminders.add"],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uniq_sorted(values: list[str]) -> list[str]:
    return sorted({v.strip() for v in values if v.strip()})


def _resolve_commands_for_group(group: str) -> list[str]:
    if group == "all":
        all_cmds: list[str] = []
        for cmds in GROUP_COMMANDS.values():
            all_cmds.extend(cmds)
        return _uniq_sorted(all_cmds)
    return _uniq_sorted(GROUP_COMMANDS.get(group, []))


def _format_group_list() -> str:
    return ", ".join(["camera", "screen", "writes", "all"])


def _parse_duration_ms(raw: str | None) -> int | None:
    if not raw:
        return None
    raw = raw.strip().lower()
    m = re.match(r"^(\d+)(s|m|h|d)$", raw)
    if not m:
        return None
    n = int(m.group(1))
    if n <= 0:
        return None
    unit = m.group(2)
    mult = {"s": 1000, "m": 60_000, "h": 3_600_000, "d": 86_400_000}[unit]
    return n * mult


def _format_duration(ms: int) -> str:
    s = max(0, ms // 1000)
    if s < 60:
        return f"{s}s"
    m = s // 60
    if m < 60:
        return f"{m}m"
    h = m // 60
    if h < 48:
        return f"{h}h"
    return f"{h // 24}d"


def _resolve_state_path(state_dir: str) -> str:
    return str(Path(state_dir) / Path(*STATE_REL_PATH))


# ---------------------------------------------------------------------------
# State file read/write
# ---------------------------------------------------------------------------

def _read_arm_state(state_path: str) -> dict | None:
    try:
        with open(state_path, encoding="utf-8") as f:
            parsed = json.load(f)
        if not isinstance(parsed, dict):
            return None
        version = parsed.get("version")
        if version not in (1, 2):
            return None
        if not isinstance(parsed.get("armedAtMs"), (int, float)):
            return None
        expires = parsed.get("expiresAtMs")
        if expires is not None and not isinstance(expires, (int, float)):
            return None
        if version == 1:
            if not isinstance(parsed.get("removedFromDeny"), list):
                return None
            return parsed
        # v2 validation
        group = parsed.get("group", "")
        if group not in ("camera", "screen", "writes", "all"):
            return None
        for field in ("armedCommands", "addedToAllow", "removedFromDeny"):
            if not isinstance(parsed.get(field), list):
                return None
        return parsed
    except Exception:
        return None


def _write_arm_state(state_path: str, state: dict | None) -> None:
    path = Path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if state is None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
        f.write("\n")


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _load_config():
    try:
        from openclaw.config.loader import load_config
        return load_config()
    except Exception:
        return None


def _config_to_dict(cfg) -> dict:
    if isinstance(cfg, dict):
        return cfg
    if hasattr(cfg, "model_dump"):
        return cfg.model_dump()
    if hasattr(cfg, "__dict__"):
        return cfg.__dict__
    return {}


def _normalize_list(cfg_dict: dict, key_path: list[str]) -> list[str]:
    obj = cfg_dict
    for k in key_path:
        if not isinstance(obj, dict):
            return []
        obj = obj.get(k) or {}
    if isinstance(obj, list):
        return _uniq_sorted([str(v) for v in obj if isinstance(v, str)])
    return []


def _get_deny_list(cfg_dict: dict) -> list[str]:
    gw = cfg_dict.get("gateway") or {}
    nodes = gw.get("nodes") or {}
    raw = nodes.get("denyCommands") or []
    return _uniq_sorted([str(v) for v in raw if isinstance(v, str)])


def _get_allow_list(cfg_dict: dict) -> list[str]:
    gw = cfg_dict.get("gateway") or {}
    nodes = gw.get("nodes") or {}
    raw = nodes.get("allowCommands") or []
    return _uniq_sorted([str(v) for v in raw if isinstance(v, str)])


def _patch_config_node_lists(
    cfg_dict: dict, allow_commands: list[str], deny_commands: list[str]
) -> dict:
    import copy
    next_cfg = copy.deepcopy(cfg_dict)
    gw = next_cfg.setdefault("gateway", {})
    nodes = gw.setdefault("nodes", {})
    nodes["allowCommands"] = allow_commands
    nodes["denyCommands"] = deny_commands
    return next_cfg


async def _write_config(cfg_dict: dict) -> None:
    try:
        from openclaw.config.loader import write_config_file
        await asyncio.get_running_loop().run_in_executor(None, write_config_file, cfg_dict)
    except Exception:
        try:
            from openclaw.gateway.config_service import write_config
            await write_config(cfg_dict)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Disarm logic
# ---------------------------------------------------------------------------

async def _disarm_now(api, state_dir: str, state_path: str, reason: str) -> dict:
    state = _read_arm_state(state_path)
    if not state:
        return {"changed": False, "restored": [], "removed": []}

    cfg = _load_config()
    cfg_dict = _config_to_dict(cfg) if cfg is not None else {}
    allow = set(_get_allow_list(cfg_dict))
    deny = set(_get_deny_list(cfg_dict))
    removed: list[str] = []
    restored: list[str] = []

    if state.get("version") == 1:
        for cmd in state.get("removedFromDeny", []):
            if cmd not in deny:
                deny.add(cmd)
                restored.append(cmd)
    else:
        for cmd in state.get("addedToAllow", []):
            if cmd in allow:
                allow.discard(cmd)
                removed.append(cmd)
        for cmd in state.get("removedFromDeny", []):
            if cmd not in deny:
                deny.add(cmd)
                restored.append(cmd)

    if removed or restored:
        next_cfg = _patch_config_node_lists(
            cfg_dict,
            _uniq_sorted(list(allow)),
            _uniq_sorted(list(deny)),
        )
        await _write_config(next_cfg)

    _write_arm_state(state_path, None)
    api.logger.info(f"phone-control: disarmed ({reason}) stateDir={state_dir}")
    return {
        "changed": bool(removed or restored),
        "removed": _uniq_sorted(removed),
        "restored": _uniq_sorted(restored),
    }


# ---------------------------------------------------------------------------
# Status formatting
# ---------------------------------------------------------------------------

def _format_status(state: dict | None) -> str:
    if not state:
        return "Phone control: disarmed."
    expires_at = state.get("expiresAtMs")
    if expires_at is None:
        until = "manual disarm required"
    else:
        remaining = max(0, int(expires_at) - int(time.time() * 1000))
        until = f"expires in {_format_duration(remaining)}"

    if state.get("version") == 1:
        cmds = _uniq_sorted(state.get("removedFromDeny", []))
    else:
        armed = state.get("armedCommands", [])
        if armed:
            cmds = _uniq_sorted(armed)
        else:
            cmds = _uniq_sorted(
                state.get("addedToAllow", []) + state.get("removedFromDeny", [])
            )

    cmd_label = ", ".join(cmds) if cmds else "none"
    return f"Phone control: armed ({until}).\nTemporarily allowed: {cmd_label}"


def _format_help() -> str:
    return "\n".join([
        "Phone control commands:",
        "",
        "/phone status",
        "/phone arm <group> [duration]",
        "/phone disarm",
        "",
        "Groups:",
        f"- {_format_group_list()}",
        "",
        "Duration format: 30s | 10m | 2h | 1d (default: 10m).",
        "",
        "Notes:",
        "- This only toggles what the gateway is allowed to invoke on phone nodes.",
        "- iOS will still ask for permissions (camera, photos, contacts, etc.) on first use.",
    ])


def _parse_group(raw: str | None) -> str | None:
    value = (raw or "").strip().lower()
    if value in ("camera", "screen", "writes", "all"):
        return value
    return None


# ---------------------------------------------------------------------------
# Resolve state dir
# ---------------------------------------------------------------------------

def _get_state_dir(api) -> str:
    try:
        runtime = getattr(api, "runtime", None)
        if runtime:
            state_rt = getattr(runtime, "state", None)
            if state_rt:
                resolve_fn = getattr(state_rt, "resolve_state_dir", None)
                if callable(resolve_fn):
                    return resolve_fn()
    except Exception:
        pass
    try:
        from openclaw.config.paths import resolve_state_dir
        return resolve_state_dir()
    except Exception:
        pass
    return str(Path.home() / ".openclaw")


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

def register(api) -> None:
    from openclaw.plugins.types import OpenClawPluginCommandDefinition, OpenClawPluginService

    _expiry_task: asyncio.Task | None = None
    _stop_event = asyncio.Event()

    async def _expiry_tick(api, state_dir: str, state_path: str) -> None:
        state = _read_arm_state(state_path)
        if not state or state.get("expiresAtMs") is None:
            return
        if time.time() * 1000 < state["expiresAtMs"]:
            return
        await _disarm_now(api, state_dir, state_path, "expired")

    async def _expiry_loop(api, state_dir: str, state_path: str, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                await _expiry_tick(api, state_dir, state_path)
            except Exception:
                pass
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=15.0)
            except TimeoutError:
                pass

    async def _service_start(ctx) -> None:
        nonlocal _expiry_task, _stop_event
        state_dir = getattr(ctx, "state_dir", None) or _get_state_dir(api)
        state_path = _resolve_state_path(state_dir)
        _stop_event = asyncio.Event()
        # Run first tick immediately, best effort
        try:
            await _expiry_tick(api, state_dir, state_path)
        except Exception:
            pass
        _expiry_task = asyncio.ensure_future(
            _expiry_loop(api, state_dir, state_path, _stop_event)
        )

    async def _service_stop(_ctx=None) -> None:
        nonlocal _expiry_task
        _stop_event.set()
        if _expiry_task is not None:
            _expiry_task.cancel()
            _expiry_task = None

    api.register_service(OpenClawPluginService(
        id="phone-control-expiry",
        start=_service_start,
        stop=_service_stop,
    ))

    async def handle_phone(ctx) -> dict:
        args = (getattr(ctx, "args", None) or "").strip()
        tokens = [t for t in args.split() if t]
        action = (tokens[0].lower() if tokens else "")

        state_dir = _get_state_dir(api)
        state_path = _resolve_state_path(state_dir)

        if not action or action == "help":
            state = _read_arm_state(state_path)
            return {"text": f"{_format_status(state)}\n\n{_format_help()}"}

        if action == "status":
            state = _read_arm_state(state_path)
            return {"text": _format_status(state)}

        if action == "disarm":
            res = await _disarm_now(api, state_dir, state_path, "manual")
            if not res["changed"]:
                return {"text": "Phone control: disarmed."}
            restored_label = ", ".join(res["restored"]) if res["restored"] else "none"
            removed_label = ", ".join(res["removed"]) if res["removed"] else "none"
            return {
                "text": (
                    f"Phone control: disarmed.\n"
                    f"Removed allowlist: {removed_label}\n"
                    f"Restored denylist: {restored_label}"
                )
            }

        if action == "arm":
            group = _parse_group(tokens[1] if len(tokens) > 1 else None)
            if not group:
                return {
                    "text": f"Usage: /phone arm <group> [duration]\nGroups: {_format_group_list()}"
                }
            duration_str = tokens[2] if len(tokens) > 2 else None
            duration_ms = _parse_duration_ms(duration_str) or 10 * 60_000
            expires_at_ms = int(time.time() * 1000) + duration_ms

            commands = _resolve_commands_for_group(group)
            cfg = _load_config()
            cfg_dict = _config_to_dict(cfg) if cfg is not None else {}

            allow_set = set(_get_allow_list(cfg_dict))
            deny_set = set(_get_deny_list(cfg_dict))

            added_to_allow: list[str] = []
            removed_from_deny: list[str] = []
            for cmd in commands:
                if cmd not in allow_set:
                    allow_set.add(cmd)
                    added_to_allow.append(cmd)
                if cmd in deny_set:
                    deny_set.discard(cmd)
                    removed_from_deny.append(cmd)

            next_cfg = _patch_config_node_lists(
                cfg_dict,
                _uniq_sorted(list(allow_set)),
                _uniq_sorted(list(deny_set)),
            )
            await _write_config(next_cfg)

            _write_arm_state(state_path, {
                "version": STATE_VERSION,
                "armedAtMs": int(time.time() * 1000),
                "expiresAtMs": expires_at_ms,
                "group": group,
                "armedCommands": _uniq_sorted(commands),
                "addedToAllow": _uniq_sorted(added_to_allow),
                "removedFromDeny": _uniq_sorted(removed_from_deny),
            })

            allowed_label = ", ".join(_uniq_sorted(commands))
            return {
                "text": (
                    f"Phone control: armed for {_format_duration(duration_ms)}.\n"
                    f"Temporarily allowed: {allowed_label}\n"
                    f"To disarm early: /phone disarm"
                )
            }

        return {"text": _format_help()}

    api.register_command(OpenClawPluginCommandDefinition(
        name="phone",
        description="Arm/disarm high-risk phone node commands (camera/screen/writes).",
        handler=handle_phone,
        accepts_args=True,
    ))


plugin = {
    "id": "phone-control",
    "name": "Phone Control",
    "description": "Arm/disarm high-risk phone node commands with optional auto-expiry.",
    "register": register,
}
