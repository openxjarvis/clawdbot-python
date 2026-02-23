"""
HTTP Hooks system — fully aligned with TypeScript openclaw/src/gateway/hooks.ts
and openclaw/src/gateway/hooks-mapping.ts.

Provides POST /hooks/wake, /hooks/agent, /hooks/<name> endpoints with:
- Token authentication (Authorization: Bearer or X-OpenClaw-Token)
- Agent and session policy enforcement
- Hook mapping engine with {{template}} variable rendering
- Gmail preset mapping support
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)

DEFAULT_HOOKS_PATH = "/hooks"
DEFAULT_HOOKS_MAX_BODY_BYTES = 256 * 1024  # 256 KB


# ---------------------------------------------------------------------------
# Config types
# ---------------------------------------------------------------------------

@dataclass
class HookAgentPolicyResolved:
    default_agent_id: str
    known_agent_ids: set[str]
    allowed_agent_ids: set[str] | None = None


@dataclass
class HookSessionPolicyResolved:
    default_session_key: str | None = None
    allow_request_session_key: bool = False
    allowed_session_key_prefixes: list[str] | None = None


@dataclass
class HooksConfigResolved:
    base_path: str
    token: str
    max_body_bytes: int
    mappings: list["HookMappingResolved"]
    agent_policy: HookAgentPolicyResolved
    session_policy: HookSessionPolicyResolved


# ---------------------------------------------------------------------------
# Mapping types
# ---------------------------------------------------------------------------

@dataclass
class HookMappingResolved:
    id: str
    match_path: str | None = None
    match_source: str | None = None
    action: str = "agent"  # "wake" | "agent"
    wake_mode: str = "now"  # "now" | "next-heartbeat"
    name: str | None = None
    agent_id: str | None = None
    session_key: str | None = None
    message_template: str | None = None
    text_template: str | None = None
    deliver: bool | None = None
    allow_unsafe_external_content: bool | None = None
    channel: str | None = None
    to: str | None = None
    model: str | None = None
    thinking: str | None = None
    timeout_seconds: int | None = None


@dataclass
class HookMappingContext:
    payload: dict[str, Any]
    headers: dict[str, str]
    url_path: str
    query: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Config resolution
# ---------------------------------------------------------------------------

def resolve_hooks_config(cfg: Any) -> "HooksConfigResolved | None":
    """Resolve hooks configuration from OpenClaw config.

    Returns None if hooks are not enabled.
    Raises ValueError if enabled but misconfigured.
    """
    hooks_cfg = getattr(cfg, "hooks", None)
    if hooks_cfg is None:
        return None

    enabled = getattr(hooks_cfg, "enabled", False)
    if not enabled:
        return None

    token = str(getattr(hooks_cfg, "token", "") or "").strip()
    if not token:
        raise ValueError("hooks.enabled requires hooks.token")

    raw_path = str(getattr(hooks_cfg, "path", "") or "").strip() or DEFAULT_HOOKS_PATH
    if not raw_path.startswith("/"):
        raw_path = "/" + raw_path
    trimmed_path = raw_path.rstrip("/") if len(raw_path) > 1 else raw_path
    if trimmed_path == "/":
        raise ValueError("hooks.path may not be '/'")

    max_body_raw = getattr(hooks_cfg, "maxBodyBytes", None)
    max_body_bytes = (
        int(max_body_raw) if isinstance(max_body_raw, (int, float)) and max_body_raw > 0
        else DEFAULT_HOOKS_MAX_BODY_BYTES
    )

    mappings = resolve_hook_mappings(hooks_cfg)

    # Agent policy
    default_agent_id = _resolve_default_agent_id(cfg)
    known_agent_ids = _resolve_known_agent_ids(cfg, default_agent_id)
    raw_allowed = getattr(hooks_cfg, "allowedAgentIds", None)
    allowed_agent_ids = _resolve_allowed_agent_ids(raw_allowed)

    # Session policy
    raw_default_sk = getattr(hooks_cfg, "defaultSessionKey", None)
    default_session_key = str(raw_default_sk).strip() if raw_default_sk else None

    raw_prefixes = getattr(hooks_cfg, "allowedSessionKeyPrefixes", None)
    allowed_prefixes = _resolve_allowed_session_key_prefixes(raw_prefixes)

    allow_request_sk = bool(getattr(hooks_cfg, "allowRequestSessionKey", False))

    # Validate default session key against allowed prefixes
    if default_session_key and allowed_prefixes:
        if not _is_session_key_allowed_by_prefix(default_session_key, allowed_prefixes):
            raise ValueError("hooks.defaultSessionKey must match hooks.allowedSessionKeyPrefixes")

    if not default_session_key and allowed_prefixes:
        if not _is_session_key_allowed_by_prefix("hook:example", allowed_prefixes):
            raise ValueError(
                "hooks.allowedSessionKeyPrefixes must include 'hook:' when "
                "hooks.defaultSessionKey is unset"
            )

    return HooksConfigResolved(
        base_path=trimmed_path,
        token=token,
        max_body_bytes=max_body_bytes,
        mappings=mappings,
        agent_policy=HookAgentPolicyResolved(
            default_agent_id=default_agent_id,
            known_agent_ids=known_agent_ids,
            allowed_agent_ids=allowed_agent_ids,
        ),
        session_policy=HookSessionPolicyResolved(
            default_session_key=default_session_key,
            allow_request_session_key=allow_request_sk,
            allowed_session_key_prefixes=allowed_prefixes,
        ),
    )


def _resolve_default_agent_id(cfg: Any) -> str:
    agents = getattr(cfg, "agents", None) or {}
    if hasattr(agents, "defaultAgent"):
        val = getattr(agents, "defaultAgent", None)
        if isinstance(val, str) and val.strip():
            return val.strip().lower()
    if isinstance(agents, dict):
        agents_dict = agents.get("agents", {})
        if agents_dict:
            return list(agents_dict.keys())[0]
    return "default"


def _resolve_known_agent_ids(cfg: Any, default_agent_id: str) -> set[str]:
    known: set[str] = {default_agent_id}
    agents = getattr(cfg, "agents", None) or {}
    agents_dict: dict[str, Any] = {}
    if isinstance(agents, dict):
        agents_dict = agents.get("agents", {})
    elif hasattr(agents, "agents"):
        agents_dict = getattr(agents, "agents") or {}
    for k in agents_dict:
        known.add(str(k).strip().lower())
    return known


def _resolve_allowed_agent_ids(raw: Any) -> set[str] | None:
    if not isinstance(raw, list):
        return None
    allowed: set[str] = set()
    for entry in raw:
        trimmed = str(entry).strip()
        if not trimmed:
            continue
        if trimmed == "*":
            return None  # wildcard means allow all
        allowed.add(trimmed.lower())
    return allowed if allowed else None


def _resolve_allowed_session_key_prefixes(raw: Any) -> list[str] | None:
    if not isinstance(raw, list):
        return None
    result: set[str] = set()
    for prefix in raw:
        normalized = str(prefix).strip().lower()
        if normalized:
            result.add(normalized)
    return list(result) if result else None


def _is_session_key_allowed_by_prefix(session_key: str, prefixes: list[str]) -> bool:
    normalized = session_key.strip().lower()
    if not normalized:
        return False
    return any(normalized.startswith(p) for p in prefixes)


# ---------------------------------------------------------------------------
# Token extraction
# ---------------------------------------------------------------------------

def extract_hook_token(headers: dict[str, str]) -> str | None:
    """Extract hook token from Authorization header or X-OpenClaw-Token."""
    auth = headers.get("authorization", "").strip()
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            return token
    header_token = headers.get("x-openclaw-token", "").strip()
    if header_token:
        return header_token
    return None


# ---------------------------------------------------------------------------
# Payload normalization
# ---------------------------------------------------------------------------

def normalize_wake_payload(
    payload: dict[str, Any],
) -> tuple[bool, dict[str, Any] | None, str | None]:
    """Validate and normalize /hooks/wake payload.

    Returns (ok, value, error).
    """
    text = str(payload.get("text", "")).strip()
    if not text:
        return False, None, "text required"
    mode = "next-heartbeat" if payload.get("mode") == "next-heartbeat" else "now"
    return True, {"text": text, "mode": mode}, None


def normalize_agent_payload(
    payload: dict[str, Any],
) -> tuple[bool, dict[str, Any] | None, str | None]:
    """Validate and normalize /hooks/agent payload.

    Returns (ok, value, error).
    """
    message = str(payload.get("message", "")).strip()
    if not message:
        return False, None, "message required"

    name_raw = payload.get("name")
    name = str(name_raw).strip() if isinstance(name_raw, str) and name_raw.strip() else "Hook"

    agent_id_raw = payload.get("agentId")
    agent_id = str(agent_id_raw).strip() if isinstance(agent_id_raw, str) and str(agent_id_raw).strip() else None

    wake_mode = "next-heartbeat" if payload.get("wakeMode") == "next-heartbeat" else "now"

    session_key_raw = payload.get("sessionKey")
    session_key = str(session_key_raw).strip() if isinstance(session_key_raw, str) and str(session_key_raw).strip() else None

    channel_raw = payload.get("channel")
    channel: str | None
    if channel_raw is None:
        channel = "last"
    elif isinstance(channel_raw, str) and channel_raw.strip():
        channel = channel_raw.strip()
    else:
        return False, None, "channel must be last|telegram|discord|slack|..."

    to_raw = payload.get("to")
    to = str(to_raw).strip() if isinstance(to_raw, str) and str(to_raw).strip() else None

    model_raw = payload.get("model")
    model = str(model_raw).strip() if isinstance(model_raw, str) and str(model_raw).strip() else None
    if model_raw is not None and not model:
        return False, None, "model required"

    deliver = payload.get("deliver") is not False

    thinking_raw = payload.get("thinking")
    thinking = str(thinking_raw).strip() if isinstance(thinking_raw, str) and str(thinking_raw).strip() else None

    timeout_raw = payload.get("timeoutSeconds")
    timeout_seconds: int | None = None
    if isinstance(timeout_raw, (int, float)) and timeout_raw > 0:
        timeout_seconds = int(timeout_raw)

    return True, {
        "message": message,
        "name": name,
        "agentId": agent_id,
        "wakeMode": wake_mode,
        "sessionKey": session_key,
        "deliver": deliver,
        "channel": channel,
        "to": to,
        "model": model,
        "thinking": thinking,
        "timeoutSeconds": timeout_seconds,
    }, None


def resolve_hook_target_agent_id(
    hooks_config: HooksConfigResolved,
    agent_id: str | None,
) -> str | None:
    """Resolve target agent ID, falling back to default if unknown."""
    raw = str(agent_id).strip() if agent_id else None
    if not raw:
        return None
    normalized = raw.lower()
    if normalized in hooks_config.agent_policy.known_agent_ids:
        return normalized
    return hooks_config.agent_policy.default_agent_id


def is_hook_agent_allowed(
    hooks_config: HooksConfigResolved,
    agent_id: str | None,
) -> bool:
    """Check if agent_id is permitted by agent policy."""
    raw = str(agent_id).strip() if agent_id else None
    if not raw:
        return True  # omitted agentId → use default, always allowed
    allowed = hooks_config.agent_policy.allowed_agent_ids
    if allowed is None:
        return True  # wildcard
    resolved = resolve_hook_target_agent_id(hooks_config, raw)
    return resolved is not None and resolved in allowed


def resolve_hook_session_key(
    hooks_config: HooksConfigResolved,
    source: str,  # "request" | "mapping"
    session_key: str | None = None,
) -> tuple[bool, str | None, str | None]:
    """Resolve session key for a hook invocation.

    Returns (ok, session_key, error).
    """
    requested = str(session_key).strip() if session_key else None
    if requested:
        if source == "request" and not hooks_config.session_policy.allow_request_session_key:
            return False, None, (
                "sessionKey is disabled for external /hooks/agent payloads; "
                "set hooks.allowRequestSessionKey=true to enable"
            )
        prefixes = hooks_config.session_policy.allowed_session_key_prefixes
        if prefixes and not _is_session_key_allowed_by_prefix(requested, prefixes):
            return False, None, f"sessionKey must start with one of: {', '.join(prefixes)}"
        return True, requested, None

    default_sk = hooks_config.session_policy.default_session_key
    if default_sk:
        return True, default_sk, None

    generated = f"hook:{uuid.uuid4()}"
    prefixes = hooks_config.session_policy.allowed_session_key_prefixes
    if prefixes and not _is_session_key_allowed_by_prefix(generated, prefixes):
        return False, None, f"sessionKey must start with one of: {', '.join(prefixes)}"
    return True, generated, None


# ---------------------------------------------------------------------------
# Mapping engine
# ---------------------------------------------------------------------------

_HOOK_PRESET_MAPPINGS: dict[str, list[dict[str, Any]]] = {
    "gmail": [
        {
            "id": "gmail",
            "match": {"path": "gmail"},
            "action": "agent",
            "wakeMode": "now",
            "name": "Gmail",
            "sessionKey": "hook:gmail:{{messages[0].id}}",
            "messageTemplate": (
                "New email from {{messages[0].from}}\n"
                "Subject: {{messages[0].subject}}\n"
                "{{messages[0].snippet}}\n"
                "{{messages[0].body}}"
            ),
        }
    ],
}


def resolve_hook_mappings(hooks_cfg: Any) -> list[HookMappingResolved]:
    """Resolve hook mapping configs, expanding presets."""
    raw_mappings: list[dict[str, Any]] = []

    mappings_attr = getattr(hooks_cfg, "mappings", None)
    if isinstance(mappings_attr, list):
        raw_mappings.extend(mappings_attr)

    presets = getattr(hooks_cfg, "presets", None) or []
    gmail_unsafe = getattr(hooks_cfg, "gmail", None)
    gmail_allow_unsafe = getattr(gmail_unsafe, "allowUnsafeExternalContent", None) if gmail_unsafe else None

    for preset in presets:
        preset_maps = _HOOK_PRESET_MAPPINGS.get(str(preset))
        if not preset_maps:
            continue
        if preset == "gmail" and isinstance(gmail_allow_unsafe, bool):
            raw_mappings.extend({**m, "allowUnsafeExternalContent": gmail_allow_unsafe} for m in preset_maps)
        else:
            raw_mappings.extend(preset_maps)

    return [_normalize_hook_mapping(m, i) for i, m in enumerate(raw_mappings)]


def _normalize_hook_mapping(raw: dict[str, Any], index: int) -> HookMappingResolved:
    mapping_id = str(raw.get("id") or "").strip() or f"mapping-{index + 1}"
    match = raw.get("match") or {}
    match_path = _normalize_match_path(match.get("path"))
    match_source = str(match.get("source") or "").strip() or None
    action = raw.get("action", "agent")
    wake_mode = raw.get("wakeMode", "now")
    return HookMappingResolved(
        id=mapping_id,
        match_path=match_path,
        match_source=match_source,
        action=action,
        wake_mode=wake_mode,
        name=raw.get("name"),
        agent_id=str(raw.get("agentId") or "").strip() or None,
        session_key=raw.get("sessionKey"),
        message_template=raw.get("messageTemplate"),
        text_template=raw.get("textTemplate"),
        deliver=raw.get("deliver"),
        allow_unsafe_external_content=raw.get("allowUnsafeExternalContent"),
        channel=raw.get("channel"),
        to=raw.get("to"),
        model=raw.get("model"),
        thinking=raw.get("thinking"),
        timeout_seconds=raw.get("timeoutSeconds"),
    )


def _normalize_match_path(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    trimmed = raw.strip()
    if not trimmed:
        return None
    return trimmed.strip("/")


def apply_hook_mappings(
    mappings: list[HookMappingResolved],
    ctx: HookMappingContext,
) -> dict[str, Any] | None:
    """Apply hook mappings to context, returning the first matching action or None."""
    for mapping in mappings:
        if not _mapping_matches(mapping, ctx):
            continue
        action = _build_action_from_mapping(mapping, ctx)
        if action is None:
            continue
        return action
    return None


def _mapping_matches(mapping: HookMappingResolved, ctx: HookMappingContext) -> bool:
    if mapping.match_path:
        if mapping.match_path != _normalize_match_path(ctx.url_path):
            return False
    if mapping.match_source:
        source = ctx.payload.get("source")
        if not isinstance(source, str) or source != mapping.match_source:
            return False
    return True


def _build_action_from_mapping(
    mapping: HookMappingResolved,
    ctx: HookMappingContext,
) -> dict[str, Any] | None:
    if mapping.action == "wake":
        text = _render_template(mapping.text_template or "", ctx)
        if not text.strip():
            return None
        return {"kind": "wake", "text": text, "mode": mapping.wake_mode}

    message = _render_template(mapping.message_template or "", ctx)
    if not message.strip():
        return None
    return {
        "kind": "agent",
        "message": message,
        "name": _render_optional(mapping.name, ctx),
        "agentId": mapping.agent_id,
        "wakeMode": mapping.wake_mode,
        "sessionKey": _render_optional(mapping.session_key, ctx),
        "deliver": mapping.deliver,
        "channel": mapping.channel,
        "to": _render_optional(mapping.to, ctx),
        "model": _render_optional(mapping.model, ctx),
        "thinking": _render_optional(mapping.thinking, ctx),
        "timeoutSeconds": mapping.timeout_seconds,
    }


_TEMPLATE_RE = re.compile(r"\{\{\s*([^}]+)\s*\}\}")


def _render_template(template: str, ctx: HookMappingContext) -> str:
    if not template:
        return ""

    def _replace(m: re.Match) -> str:
        expr = m.group(1).strip()
        value = _resolve_template_expr(expr, ctx)
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float, bool)):
            return str(value)
        return json.dumps(value)

    return _TEMPLATE_RE.sub(_replace, template)


def _render_optional(value: str | None, ctx: HookMappingContext) -> str | None:
    if not value:
        return None
    rendered = _render_template(value, ctx).strip()
    return rendered or None


def _resolve_template_expr(expr: str, ctx: HookMappingContext) -> Any:
    if expr == "path":
        return ctx.url_path
    if expr == "now":
        return datetime.now(UTC).isoformat()
    if expr.startswith("headers."):
        return _get_by_path(ctx.headers, expr[len("headers."):])
    if expr.startswith("query."):
        return _get_by_path(ctx.query, expr[len("query."):])
    if expr.startswith("payload."):
        return _get_by_path(ctx.payload, expr[len("payload."):])
    return _get_by_path(ctx.payload, expr)


def _get_by_path(obj: Any, path_expr: str) -> Any:
    if not path_expr:
        return None
    parts: list[str | int] = []
    for segment in re.findall(r"([^.\[\]]+)|\[(\d+)\]", path_expr):
        if segment[0]:
            parts.append(segment[0])
        elif segment[1]:
            parts.append(int(segment[1]))
    current: Any = obj
    for part in parts:
        if current is None:
            return None
        if isinstance(part, int):
            if not isinstance(current, list) or part >= len(current):
                return None
            current = current[part]
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


# ---------------------------------------------------------------------------
# HTTP endpoint handler (aiohttp / starlette compatible)
# ---------------------------------------------------------------------------

async def handle_hook_request(
    *,
    method: str,
    path: str,
    headers: dict[str, str],
    body: bytes,
    hooks_config: HooksConfigResolved,
    gateway: Any,
) -> dict[str, Any]:
    """Process an inbound HTTP hook request.

    Returns a response dict with keys: status (int), body (dict).
    """
    # Token authentication
    token = extract_hook_token(headers)
    if token != hooks_config.token:
        return {"status": 401, "body": {"error": "unauthorized"}}

    # Read JSON body
    if len(body) > hooks_config.max_body_bytes:
        return {"status": 413, "body": {"error": "payload too large"}}

    try:
        payload: dict[str, Any] = json.loads(body) if body else {}
        if not isinstance(payload, dict):
            payload = {}
    except json.JSONDecodeError as exc:
        return {"status": 400, "body": {"error": f"invalid JSON: {exc}"}}

    # Normalize headers
    normalized_headers = {k.lower(): v for k, v in headers.items()}

    # Build mapping context
    base_path = hooks_config.base_path
    rel_path = path[len(base_path):].lstrip("/") if path.startswith(base_path) else path.lstrip("/")
    ctx = HookMappingContext(
        payload=payload,
        headers=normalized_headers,
        url_path=rel_path,
    )

    # Check for named mapping first
    if rel_path and rel_path not in ("wake", "agent"):
        mapped_action = apply_hook_mappings(hooks_config.mappings, ctx)
        if mapped_action is not None:
            return await _dispatch_hook_action(mapped_action, hooks_config, gateway, source="mapping")
        return {"status": 404, "body": {"error": f"unknown hook path: {rel_path!r}"}}

    if rel_path == "wake":
        ok, wake_val, error = normalize_wake_payload(payload)
        if not ok:
            return {"status": 400, "body": {"error": error}}
        action = {"kind": "wake", "text": wake_val["text"], "mode": wake_val["mode"]}
        return await _dispatch_hook_action(action, hooks_config, gateway, source="request")

    if rel_path == "agent":
        ok, agent_val, error = normalize_agent_payload(payload)
        if not ok:
            return {"status": 400, "body": {"error": error}}
        assert agent_val is not None
        # Agent policy check
        if not is_hook_agent_allowed(hooks_config, agent_val.get("agentId")):
            return {"status": 403, "body": {"error": "agentId is not allowed by hooks.allowedAgentIds"}}
        # Session key policy
        ok_sk, session_key, sk_error = resolve_hook_session_key(
            hooks_config, "request", agent_val.get("sessionKey")
        )
        if not ok_sk:
            return {"status": 400, "body": {"error": sk_error}}
        action = {**agent_val, "kind": "agent", "sessionKey": session_key}
        return await _dispatch_hook_action(action, hooks_config, gateway, source="request")

    # Root hooks path — try mappings
    mapped_action = apply_hook_mappings(hooks_config.mappings, ctx)
    if mapped_action is not None:
        return await _dispatch_hook_action(mapped_action, hooks_config, gateway, source="mapping")

    return {"status": 404, "body": {"error": "no matching hook"}}


async def _dispatch_hook_action(
    action: dict[str, Any],
    hooks_config: HooksConfigResolved,
    gateway: Any,
    source: str,
) -> dict[str, Any]:
    """Dispatch a resolved hook action to the gateway."""
    kind = action.get("kind")

    if kind == "wake":
        text = str(action.get("text", "")).strip()
        if not text:
            return {"status": 400, "body": {"error": "text required for wake"}}
        mode = action.get("mode", "now")
        try:
            if hasattr(gateway, "enqueue_wake_event"):
                await gateway.enqueue_wake_event(text=text, mode=mode)
            else:
                await gateway.broadcast_event("wake", {"text": text, "mode": mode})
        except Exception as exc:
            logger.error(f"Hook wake dispatch error: {exc}", exc_info=True)
            return {"status": 500, "body": {"error": str(exc)}}
        return {"status": 200, "body": {"ok": True, "action": "wake", "mode": mode}}

    if kind == "agent":
        message = str(action.get("message", "")).strip()
        if not message:
            return {"status": 400, "body": {"error": "message required"}}

        agent_id_raw = action.get("agentId")
        resolved_agent_id = (
            resolve_hook_target_agent_id(hooks_config, agent_id_raw)
            or hooks_config.agent_policy.default_agent_id
        )

        # Resolve session key (from mapping, already resolved)
        session_key = action.get("sessionKey")
        if not session_key:
            ok_sk, session_key, sk_error = resolve_hook_session_key(hooks_config, source)
            if not ok_sk:
                return {"status": 400, "body": {"error": sk_error}}

        run_id = f"hook:{uuid.uuid4()}"
        try:
            if hasattr(gateway, "run_agent_command"):
                await gateway.run_agent_command(
                    message=message,
                    session_key=session_key,
                    agent_id=resolved_agent_id,
                    run_id=run_id,
                    deliver=action.get("deliver", True),
                    channel=action.get("channel"),
                    to=action.get("to"),
                    model=action.get("model"),
                    thinking=action.get("thinking"),
                    timeout_seconds=action.get("timeoutSeconds"),
                )
            else:
                logger.warning("Gateway has no run_agent_command; broadcasting hook.agent event")
                await gateway.broadcast_event("hook.agent", {
                    "runId": run_id,
                    "message": message,
                    "sessionKey": session_key,
                    "agentId": resolved_agent_id,
                })
        except Exception as exc:
            logger.error(f"Hook agent dispatch error: {exc}", exc_info=True)
            return {"status": 500, "body": {"error": str(exc)}}

        return {"status": 200, "body": {"ok": True, "action": "agent", "runId": run_id}}

    return {"status": 400, "body": {"error": f"unknown action kind: {kind!r}"}}
