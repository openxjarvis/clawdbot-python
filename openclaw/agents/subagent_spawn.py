"""Subagent spawning logic

Fully aligned with TypeScript openclaw/src/agents/subagent-spawn.ts

This module implements the core logic for spawning sub-agent sessions:
- Depth validation (prevent infinite nesting)
- Active children limit enforcement
- Cross-agent allowlist verification
- Model selection and configuration
- Session key generation and registration
- Gateway RPC integration for agent runs
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any, Literal

from openclaw.routing.session_key import (
    normalize_agent_id,
    parse_agent_session_key,
)
from openclaw.agents.model_selection import (
    resolve_subagent_spawn_model_selection,
)

logger = logging.getLogger(__name__)

# Constants
SUBAGENT_SPAWN_ACCEPTED_NOTE = (
    "auto-announces on completion, do not poll/sleep. "
    "The response will be sent back as an agent message."
)
SUBAGENT_SPAWN_SESSION_ACCEPTED_NOTE = (
    "thread-bound session stays active after completion. "
    "Results are auto-announced."
)

SUBAGENT_SPAWN_MODES: list[str] = ["run", "session"]
AGENT_LANE_SUBAGENT = "subagent"


SpawnSubagentMode = Literal["run", "session"]


@dataclass
class SpawnSubagentParams:
    """Parameters for spawning a subagent (mirrors TS SpawnSubagentParams)"""
    
    task: str
    label: str | None = None
    agentId: str | None = None
    model: str | None = None
    thinking: str | None = None
    runTimeoutSeconds: int | None = None
    cleanup: Literal["delete", "keep"] = "keep"
    expectsCompletionMessage: bool = False
    mode: SpawnSubagentMode = "run"
    thread: bool = False


@dataclass
class SpawnSubagentContext:
    """Context for spawning a subagent (mirrors TS SpawnSubagentContext)"""
    
    agentSessionKey: str | None = None
    agentChannel: str | None = None
    agentAccountId: str | None = None
    agentTo: str | None = None
    agentThreadId: str | int | None = None
    agentGroupId: str | None = None
    agentGroupChannel: str | None = None
    agentGroupSpace: str | None = None
    requesterAgentIdOverride: str | None = None


@dataclass
class SpawnSubagentResult:
    """Result of spawning a subagent (mirrors TS SpawnSubagentResult)"""
    
    status: Literal["accepted", "forbidden", "error"]
    childSessionKey: str | None = None
    runId: str | None = None
    note: str | None = None
    modelApplied: bool | None = None
    error: str | None = None


def split_model_ref(ref: str | None) -> dict[str, str | None]:
    """
    Split a model reference into provider and model.
    
    Examples:
        "openai/gpt-4" -> {"provider": "openai", "model": "gpt-4"}
        "gpt-4" -> {"provider": None, "model": "gpt-4"}
        None -> {"provider": None, "model": None}
    
    Mirrors TS splitModelRef() from subagent-spawn.ts lines 55-68
    """
    if not ref:
        return {"provider": None, "model": None}
    
    trimmed = ref.strip()
    if not trimmed:
        return {"provider": None, "model": None}
    
    parts = trimmed.split("/", 1)
    if len(parts) == 2:
        return {"provider": parts[0], "model": parts[1]}
    
    return {"provider": None, "model": trimmed}


def normalize_delivery_context(
    channel: str | None = None,
    to: str | None = None,
    account_id: str | None = None,
    thread_id: str | int | None = None,
) -> dict[str, Any] | None:
    """
    Normalize delivery context (mirrors TS normalizeDeliveryContext).
    
    Returns None if all fields are empty.
    """
    normalized: dict[str, Any] = {}
    
    if channel and isinstance(channel, str):
        normalized["channel"] = channel.strip()
    if to and isinstance(to, str):
        normalized["to"] = to.strip()
    if account_id and isinstance(account_id, str):
        normalized["accountId"] = account_id.strip()
    if thread_id is not None:
        if isinstance(thread_id, int):
            normalized["threadId"] = thread_id
        elif isinstance(thread_id, str) and thread_id.strip():
            normalized["threadId"] = thread_id.strip()
    
    return normalized if normalized else None


def resolve_main_session_alias(cfg: Any) -> dict[str, str]:
    """
    Resolve main session alias from config.
    
    Returns:
        {"mainKey": str, "alias": str}
    
    Mirrors TS resolveMainSessionAlias from sessions-helpers.ts
    """
    main_key = "main"  # Default
    
    if hasattr(cfg, "session") and hasattr(cfg.session, "mainKey"):
        raw = cfg.session.mainKey
        if isinstance(raw, str) and raw.strip():
            main_key = raw.strip()
    elif isinstance(cfg, dict):
        session_cfg = cfg.get("session", {})
        if isinstance(session_cfg, dict):
            raw = session_cfg.get("mainKey")
            if isinstance(raw, str) and raw.strip():
                main_key = raw.strip()
    
    # Resolve default agent ID
    default_agent_id = "main"
    if hasattr(cfg, "agents") and hasattr(cfg.agents, "defaultId"):
        raw_id = cfg.agents.defaultId
        if isinstance(raw_id, str) and raw_id.strip():
            default_agent_id = normalize_agent_id(raw_id)
    elif isinstance(cfg, dict):
        agents_cfg = cfg.get("agents", {})
        if isinstance(agents_cfg, dict):
            raw_id = agents_cfg.get("defaultId")
            if isinstance(raw_id, str) and raw_id.strip():
                default_agent_id = normalize_agent_id(raw_id)
    
    alias = f"agent:{default_agent_id}:{main_key}"
    
    return {"mainKey": main_key, "alias": alias}


def resolve_internal_session_key(
    key: str,
    alias: str,
    main_key: str,
) -> str:
    """
    Resolve internal session key (expand shortcuts).
    
    Mirrors TS resolveInternalSessionKey from sessions-helpers.ts
    """
    trimmed = key.strip()
    if not trimmed:
        return alias
    
    # Already internal format
    if trimmed.startswith("agent:") or trimmed.startswith("subagent:"):
        return trimmed
    
    # Shortcut like "main" -> expand to alias
    if trimmed == main_key or trimmed == "main":
        return alias
    
    return trimmed


def resolve_display_session_key(
    key: str,
    alias: str,
    main_key: str,
) -> str:
    """
    Resolve display session key (collapse to shortcut if main).
    
    Mirrors TS resolveDisplaySessionKey from sessions-helpers.ts
    """
    trimmed = key.strip()
    if trimmed == alias:
        return main_key
    return trimmed


def resolve_agent_config(cfg: Any, agent_id: str) -> dict[str, Any] | None:
    """
    Resolve configuration for a specific agent.
    
    Mirrors TS resolveAgentConfig from agent-scope.ts
    """
    if hasattr(cfg, "agents") and hasattr(cfg.agents, "agents"):
        agents_list = cfg.agents.agents
        if isinstance(agents_list, list):
            for agent in agents_list:
                if isinstance(agent, dict) and agent.get("id") == agent_id:
                    return agent
        elif isinstance(agents_list, dict):
            return agents_list.get(agent_id)
    
    if isinstance(cfg, dict):
        agents_cfg = cfg.get("agents", {})
        if isinstance(agents_cfg, dict):
            agents_list = agents_cfg.get("agents", [])
            if isinstance(agents_list, list):
                for agent in agents_list:
                    if isinstance(agent, dict) and agent.get("id") == agent_id:
                        return agent
            elif isinstance(agents_list, dict):
                return agents_list.get(agent_id)
    
    return None


def get_subagent_depth_from_session_store(
    session_key: str | None,
    cfg: Any = None,
    gateway: Any = None,
) -> int:
    """
    Get subagent depth from session store (mirrors TS getSubagentDepthFromSessionStore).
    
    This function reads the spawnDepth field from the session store or walks
    the spawnedBy chain to compute depth. Falls back to counting ":subagent:"
    in the session key.
    
    Args:
        session_key: Session key to check
        cfg: Config instance
        gateway: Gateway instance (for accessing session store)
    
    Returns:
        Depth as integer (0 = main session, 1 = subagent, 2 = sub-subagent, etc.)
    """
    from openclaw.routing.session_key import get_subagent_depth
    
    raw = (session_key or "").strip()
    fallback_depth = get_subagent_depth(raw)
    
    if not raw:
        return fallback_depth
    
    # Try to read from session store
    if gateway and hasattr(gateway, "session_manager"):
        try:
            session_manager = gateway.session_manager
            if hasattr(session_manager, "get_session_entry"):
                entry = session_manager.get_session_entry(raw)
                if isinstance(entry, dict):
                    # Check spawnDepth field first
                    spawn_depth = entry.get("spawnDepth")
                    if isinstance(spawn_depth, int) and spawn_depth >= 0:
                        return spawn_depth
                    
                    # Walk spawnedBy chain
                    spawned_by = entry.get("spawnedBy")
                    if isinstance(spawned_by, str) and spawned_by.strip():
                        parent_depth = get_subagent_depth_from_session_store(
                            spawned_by.strip(),
                            cfg=cfg,
                            gateway=gateway,
                        )
                        return parent_depth + 1
        except Exception as e:
            logger.debug(f"Failed to read session store for depth: {e}")
    
    return fallback_depth


async def spawn_subagent_direct(
    params: SpawnSubagentParams,
    ctx: SpawnSubagentContext,
    *,
    cfg: Any = None,
    gateway: Any = None,
) -> SpawnSubagentResult:
    """
    Spawn a subagent session directly.
    
    This is the core spawning logic, fully aligned with TypeScript
    spawnSubagentDirect() from openclaw/src/agents/subagent-spawn.ts lines 70-305.
    
    Args:
        params: Spawn parameters
        ctx: Spawn context (requester info)
        cfg: OpenClaw configuration
        gateway: Gateway server instance
    
    Returns:
        SpawnSubagentResult with status, childSessionKey, runId, etc.
    """
    from openclaw.config.unified import load_config
    from openclaw.auto_reply.reply.thinking import normalize_think_level, format_thinking_levels
    
    # Load config if not provided
    if cfg is None:
        cfg = load_config()
    
    # Validate parameters
    task = params.task
    label = (params.label or "").strip()
    requested_agent_id = params.agentId
    model_override = params.model
    thinking_override_raw = params.thinking
    cleanup = params.cleanup if params.cleanup in ("keep", "delete") else "keep"
    
    # Normalize delivery context (mirrors TS lines 81-86)
    requester_origin = normalize_delivery_context(
        channel=ctx.agentChannel,
        to=ctx.agentTo,
        account_id=ctx.agentAccountId,
        thread_id=ctx.agentThreadId,
    )
    
    run_timeout_seconds = 0
    if isinstance(params.runTimeoutSeconds, int) and params.runTimeoutSeconds >= 0:
        run_timeout_seconds = params.runTimeoutSeconds
    
    model_applied = False
    
    # Resolve session aliases (mirrors TS lines 93-107)
    main_session_data = resolve_main_session_alias(cfg)
    main_key = main_session_data["mainKey"]
    alias = main_session_data["alias"]
    
    requester_session_key = ctx.agentSessionKey
    requester_internal_key = (
        resolve_internal_session_key(requester_session_key, alias, main_key)
        if requester_session_key
        else alias
    )
    requester_display_key = resolve_display_session_key(
        requester_internal_key,
        alias,
        main_key,
    )
    
    # Depth validation (mirrors TS lines 109-116)
    caller_depth = get_subagent_depth_from_session_store(
        requester_internal_key,
        cfg=cfg,
        gateway=gateway,
    )
    
    max_spawn_depth = 1  # Default
    if hasattr(cfg, "agents") and hasattr(cfg.agents, "defaults"):
        defaults = cfg.agents.defaults
        if hasattr(defaults, "subagents"):
            subagents_cfg = defaults.subagents
            if isinstance(subagents_cfg, dict):
                max_spawn_depth = subagents_cfg.get("maxSpawnDepth", 1)
            elif hasattr(subagents_cfg, "maxSpawnDepth"):
                max_spawn_depth = subagents_cfg.maxSpawnDepth or 1
    elif isinstance(cfg, dict):
        max_spawn_depth = (
            cfg.get("agents", {})
            .get("defaults", {})
            .get("subagents", {})
            .get("maxSpawnDepth", 1)
        )
    
    if caller_depth >= max_spawn_depth:
        return SpawnSubagentResult(
            status="forbidden",
            error=f"sessions_spawn is not allowed at this depth (current depth: {caller_depth}, max: {max_spawn_depth})",
        )
    
    # Active children limit (mirrors TS lines 118-125)
    max_children = 5  # Default
    if hasattr(cfg, "agents") and hasattr(cfg.agents, "defaults"):
        defaults = cfg.agents.defaults
        if hasattr(defaults, "subagents"):
            subagents_cfg = defaults.subagents
            if isinstance(subagents_cfg, dict):
                max_children = subagents_cfg.get("maxChildrenPerAgent", 5)
            elif hasattr(subagents_cfg, "maxChildrenPerAgent"):
                max_children = subagents_cfg.maxChildrenPerAgent or 5
    elif isinstance(cfg, dict):
        max_children = (
            cfg.get("agents", {})
            .get("defaults", {})
            .get("subagents", {})
            .get("maxChildrenPerAgent", 5)
        )
    
    # Count active children (requires registry)
    from openclaw.agents.subagent_registry import get_global_registry
    
    registry = get_global_registry()
    active_children = registry.count_active_runs_for_session(requester_internal_key)
    
    if active_children >= max_children:
        return SpawnSubagentResult(
            status="forbidden",
            error=f"sessions_spawn has reached max active children for this session ({active_children}/{max_children})",
        )
    
    # Resolve requester and target agent IDs (mirrors TS lines 127-130)
    requester_agent_id = normalize_agent_id(
        ctx.requesterAgentIdOverride
        or (parse_agent_session_key(requester_internal_key) or {}).get("agent_id")
    )
    target_agent_id = (
        normalize_agent_id(requested_agent_id)
        if requested_agent_id
        else requester_agent_id
    )
    
    # Cross-agent allowlist validation (mirrors TS lines 131-147)
    if target_agent_id != requester_agent_id:
        agent_config = resolve_agent_config(cfg, requester_agent_id)
        allow_agents: list[str] = []
        
        if isinstance(agent_config, dict):
            subagents_cfg = agent_config.get("subagents", {})
            if isinstance(subagents_cfg, dict):
                allow_agents = subagents_cfg.get("allowAgents", [])
        
        allow_any = any(v.strip() == "*" for v in allow_agents)
        normalized_target_id = target_agent_id.lower()
        allow_set = {
            normalize_agent_id(v).lower()
            for v in allow_agents
            if v.strip() and v.strip() != "*"
        }
        
        if not allow_any and normalized_target_id not in allow_set:
            allowed_text = ", ".join(sorted(allow_set)) if allow_set else "none"
            return SpawnSubagentResult(
                status="forbidden",
                error=f"agentId is not allowed for sessions_spawn (allowed: {allowed_text})",
            )
    
    # Validate mode (mirrors TS lines ~148-155)
    mode = params.mode if params.mode in SUBAGENT_SPAWN_MODES else "run"

    # Generate child session key (mirrors TS line 148)
    child_session_key = f"agent:{target_agent_id}:subagent:{uuid.uuid4()}"
    child_depth = caller_depth + 1
    spawned_by_key = requester_internal_key
    
    # Resolve model (mirrors TS lines 151-156)
    target_agent_config = resolve_agent_config(cfg, target_agent_id)
    resolved_model = resolve_subagent_spawn_model_selection(
        cfg=cfg,
        agent_id=target_agent_id,
        model_override=model_override,
    )
    
    # Resolve thinking level (mirrors TS lines 158-175)
    resolved_thinking_default_raw: str | None = None
    if isinstance(target_agent_config, dict):
        subagents_cfg = target_agent_config.get("subagents", {})
        if isinstance(subagents_cfg, dict):
            resolved_thinking_default_raw = subagents_cfg.get("thinking")
    
    if not resolved_thinking_default_raw and isinstance(cfg, dict):
        resolved_thinking_default_raw = (
            cfg.get("agents", {})
            .get("defaults", {})
            .get("subagents", {})
            .get("thinking")
        )
    
    thinking_override: str | None = None
    thinking_candidate_raw = thinking_override_raw or resolved_thinking_default_raw
    
    if thinking_candidate_raw:
        normalized_thinking = normalize_think_level(thinking_candidate_raw)
        if not normalized_thinking:
            provider_model = split_model_ref(resolved_model)
            hint = format_thinking_levels(
                provider_model.get("provider"),
                provider_model.get("model"),
            )
            return SpawnSubagentResult(
                status="error",
                error=f'Invalid thinking level "{thinking_candidate_raw}". Use one of: {hint}.',
            )
        thinking_override = normalized_thinking
    
    # Gateway RPC: Patch session with spawnDepth (mirrors TS lines 176-190)
    if gateway is not None:
        try:
            # Call sessions.patch handler directly
            from openclaw.gateway.api.sessions_methods import SessionsPatchMethod
            
            patch_method = SessionsPatchMethod()
            mock_connection = type("MockConnection", (), {"gateway": gateway})()
            
            await patch_method.execute(
                mock_connection,
                {
                    "key": child_session_key,
                    "patch": {"spawnDepth": child_depth},
                },
            )
        except Exception as err:
            message_text = str(err)
            return SpawnSubagentResult(
                status="error",
                error=message_text,
                childSessionKey=child_session_key,
            )
    
    # Gateway RPC: Patch session with model (mirrors TS lines 192-209)
    if resolved_model and gateway is not None:
        try:
            from openclaw.gateway.api.sessions_methods import SessionsPatchMethod
            
            patch_method = SessionsPatchMethod()
            mock_connection = type("MockConnection", (), {"gateway": gateway})()
            
            await patch_method.execute(
                mock_connection,
                {
                    "key": child_session_key,
                    "patch": {"model": resolved_model},
                },
            )
            model_applied = True
        except Exception as err:
            message_text = str(err)
            return SpawnSubagentResult(
                status="error",
                error=message_text,
                childSessionKey=child_session_key,
            )
    
    # Gateway RPC: Patch session with thinking level (mirrors TS lines 210-229)
    if thinking_override is not None and gateway is not None:
        try:
            from openclaw.gateway.api.sessions_methods import SessionsPatchMethod
            
            patch_method = SessionsPatchMethod()
            mock_connection = type("MockConnection", (), {"gateway": gateway})()
            
            thinking_level_value = None if thinking_override == "off" else thinking_override
            
            await patch_method.execute(
                mock_connection,
                {
                    "key": child_session_key,
                    "patch": {"thinkingLevel": thinking_level_value},
                },
            )
        except Exception as err:
            message_text = str(err)
            return SpawnSubagentResult(
                status="error",
                error=message_text,
                childSessionKey=child_session_key,
            )
    
    # Build subagent system prompt (mirrors TS lines 230-238)
    from openclaw.agents.subagent_announce import build_subagent_system_prompt
    
    child_system_prompt = build_subagent_system_prompt(
        requester_session_key=requester_session_key,
        requester_origin=requester_origin,
        child_session_key=child_session_key,
        label=label or None,
        task=task,
        child_depth=child_depth,
        max_spawn_depth=max_spawn_depth,
    )
    
    # Build child task message (mirrors TS lines 239-242)
    child_task_message = "\n\n".join([
        f"[Subagent Context] You are running as a subagent (depth {child_depth}/{max_spawn_depth}). "
        "Results auto-announce to your requester; do not busy-poll for status.",
        f"[Subagent Task]: {task}",
    ])
    
    # Thread binding for session mode (mirrors TS ensureThreadBindingForSubagentSpawn)
    if mode == "session" and params.thread and gateway is not None:
        try:
            from openclaw.gateway.api.sessions_methods import SessionsPatchMethod

            patch_method = SessionsPatchMethod()
            mock_connection = type("MockConnection", (), {"gateway": gateway})()
            thread_id = ctx.agentThreadId or str(uuid.uuid4())
            await patch_method.execute(
                mock_connection,
                {
                    "key": child_session_key,
                    "patch": {"threadId": str(thread_id), "threadBound": True},
                },
            )
            logger.debug("Thread binding set for session-mode subagent %s", child_session_key)
        except Exception as exc:
            logger.warning("Thread binding failed for %s: %s", child_session_key, exc)

    # In session mode, override cleanup to "keep" (session stays after completion)
    if mode == "session":
        cleanup = "keep"

    # Launch agent run (mirrors TS lines 244-282)
    child_idem = str(uuid.uuid4())
    child_run_id = child_idem
    
    if gateway is not None:
        try:
            # Call agent handler directly
            from openclaw.gateway.handlers import handle_agent
            
            mock_connection = type("MockConnection", (), {"gateway": gateway})()
            
            agent_params = {
                "message": child_task_message,
                "sessionKey": child_session_key,
                "channel": requester_origin.get("channel") if requester_origin else None,
                "to": requester_origin.get("to") if requester_origin else None,
                "accountId": requester_origin.get("accountId") if requester_origin else None,
                "threadId": str(requester_origin.get("threadId")) if requester_origin and requester_origin.get("threadId") is not None else None,
                "idempotencyKey": child_idem,
                "deliver": False,
                "lane": AGENT_LANE_SUBAGENT,
                "extraSystemPrompt": child_system_prompt,
                "thinking": thinking_override,
                "timeout": run_timeout_seconds if run_timeout_seconds > 0 else None,
                "label": label or None,
                "spawnedBy": spawned_by_key,
                "groupId": ctx.agentGroupId,
                "groupChannel": ctx.agentGroupChannel,
                "groupSpace": ctx.agentGroupSpace,
            }
            
            response = await handle_agent(mock_connection, agent_params)
            
            if isinstance(response, dict) and "runId" in response:
                child_run_id = response["runId"]
        
        except Exception as err:
            message_text = str(err)
            return SpawnSubagentResult(
                status="error",
                error=message_text,
                childSessionKey=child_session_key,
                runId=child_run_id,
            )
    
    # Register in subagent registry (mirrors TS lines 284-296)
    registry.register_subagent_run(
        child_session_key=child_session_key,
        requester_session_key=requester_internal_key,
        task=task,
        requester_origin=requester_origin,
        requester_display_key=requester_display_key,
        cleanup=cleanup,
        label=label or None,
        model=resolved_model,
        run_timeout_seconds=run_timeout_seconds if run_timeout_seconds > 0 else None,
        expects_completion_message=params.expectsCompletionMessage,
    )
    
    # Return success (mirrors TS lines 298-304)
    note = SUBAGENT_SPAWN_SESSION_ACCEPTED_NOTE if mode == "session" else SUBAGENT_SPAWN_ACCEPTED_NOTE
    return SpawnSubagentResult(
        status="accepted",
        childSessionKey=child_session_key,
        runId=child_run_id,
        note=note,
        modelApplied=model_applied if resolved_model else None,
    )
