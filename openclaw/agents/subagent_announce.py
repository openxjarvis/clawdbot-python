"""Subagent completion announcement

Fully aligned with TypeScript openclaw/src/agents/subagent-announce.ts

This module handles announcing subagent completion back to the requester session:
- Wait for subagent completion
- Read subagent output
- Build announcement message with stats
- Deliver via queue/steer/direct paths
- Handle cleanup (delete or keep session)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal

logger = logging.getLogger(__name__)

# Constants
SILENT_REPLY_TOKEN = "◻️"

SubagentDeliveryPath = Literal["queued", "steered", "direct", "none"]
SubagentAnnounceType = Literal["subagent task", "cron job"]


def build_subagent_system_prompt(
    *,
    requester_session_key: str | None = None,
    requester_origin: dict[str, Any] | None = None,
    child_session_key: str,
    label: str | None = None,
    task: str | None = None,
    child_depth: int = 1,
    max_spawn_depth: int = 1,
) -> str:
    """
    Build system prompt for subagent.
    
    Mirrors TS buildSubagentSystemPrompt() from subagent-announce.ts lines 594-681
    
    Args:
        requester_session_key: Parent session key
        requester_origin: Parent origin context
        child_session_key: Child session key
        label: Optional label
        task: Task description
        child_depth: Depth of child (1 = subagent, 2 = sub-subagent)
        max_spawn_depth: Maximum allowed depth
    
    Returns:
        System prompt string
    """
    task_text = (
        task.replace("  ", " ").strip()
        if task and task.strip()
        else "{{TASK_DESCRIPTION}}"
    )
    
    can_spawn = child_depth < max_spawn_depth
    parent_label = "parent orchestrator" if child_depth >= 2 else "main agent"
    
    lines = [
        "# Subagent Context",
        "",
        f"You are a **subagent** spawned by the {parent_label} for a specific task.",
        "",
        "## Your Role",
        f"- You were created to handle: {task_text}",
        "- Complete this task. That's your entire purpose.",
        f"- You are NOT the {parent_label}. Don't try to be.",
        "",
        "## Rules",
        "1. **Stay focused** - Do your assigned task, nothing else",
        f"2. **Complete the task** - Your final message will be automatically reported to the {parent_label}",
        "3. **Don't initiate** - No heartbeats, no proactive actions, no side quests",
        "4. **Be ephemeral** - You may be terminated after task completion. That's fine.",
        "5. **Trust push-based completion** - Descendant results are auto-announced back to you; do not busy-poll for status.",
        "6. **Recover from compacted/truncated tool output** - If you see `[compacted: tool output removed to free context]` or `[truncated: output exceeded context limit]`, assume prior output was reduced. Re-read only what you need using smaller chunks (`read` with offset/limit, or targeted `rg`/`head`/`tail`) instead of full-file `cat`.",
        "",
        "## Output Format",
        "When complete, your final response should include:",
        "- What you accomplished or found",
        f"- Any relevant details the {parent_label} should know",
        "- Keep it concise but informative",
        "",
        "## What You DON'T Do",
        f"- NO user conversations (that's {parent_label}'s job)",
        "- NO external messages (email, tweets, etc.) unless explicitly tasked with a specific recipient/channel",
        "- NO cron jobs or persistent state",
        f"- NO pretending to be the {parent_label}",
        f"- Only use the `message` tool when explicitly instructed to contact a specific external recipient; otherwise return plain text and let the {parent_label} deliver it",
        "",
    ]
    
    if can_spawn:
        lines.extend([
            "## Sub-Agent Spawning",
            "You CAN spawn your own sub-agents for parallel or complex work using `sessions_spawn`.",
            "Use the `subagents` tool to steer, kill, or do an on-demand status check for your spawned sub-agents.",
            "Your sub-agents will announce their results back to you automatically (not to the main agent).",
            "Default workflow: spawn work, continue orchestrating, and wait for auto-announced completions.",
            "Do NOT repeatedly poll `subagents list` in a loop unless you are actively debugging or intervening.",
            "Coordinate their work and synthesize results before reporting back.",
            "",
        ])
    elif child_depth >= 2:
        lines.extend([
            "## Sub-Agent Spawning",
            "You are a leaf worker and CANNOT spawn further sub-agents. Focus on your assigned task.",
            "",
        ])
    
    lines.append("## Session Context")
    if label:
        lines.append(f"- Label: {label}")
    if requester_session_key:
        lines.append(f"- Requester session: {requester_session_key}.")
    if requester_origin and requester_origin.get("channel"):
        lines.append(f"- Requester channel: {requester_origin['channel']}.")
    lines.append(f"- Your session: {child_session_key}.")
    lines.append("")
    
    return "\n".join(lines)


def format_duration_short(value_ms: int | None) -> str:
    """Format duration in short form (mirrors TS formatDurationShort lines 197-212)"""
    if not value_ms or value_ms <= 0:
        return "n/a"
    
    total_seconds = round(value_ms / 1000)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    
    if hours > 0:
        return f"{hours}h{minutes}m"
    if minutes > 0:
        return f"{minutes}m{seconds}s"
    return f"{seconds}s"


def format_token_count(value: int | None) -> str:
    """Format token count in compact form (mirrors TS formatTokenCount lines 214-225)"""
    if not value or value <= 0:
        return "0"
    
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}m"
    if value >= 1_000:
        return f"{value / 1_000:.1f}k"
    return str(round(value))


async def build_compact_announce_stats_line(
    session_key: str,
    started_at: int | None,
    ended_at: int | None,
    gateway: Any = None,
) -> str:
    """
    Build compact stats line for announce message.
    
    Mirrors TS buildCompactAnnounceStatsLine() from subagent-announce.ts lines 227-265
    
    Args:
        session_key: Child session key
        started_at: Start timestamp (ms)
        ended_at: End timestamp (ms)
        gateway: Gateway instance
    
    Returns:
        Stats line string like "Stats: runtime 5s • tokens 1.2k (in 800 / out 400)"
    """
    # Read session entry to get token counts
    input_tokens = 0
    output_tokens = 0
    total_tokens = None
    
    if gateway and hasattr(gateway, "session_manager"):
        try:
            session_manager = gateway.session_manager
            if hasattr(session_manager, "get_session_entry"):
                entry = session_manager.get_session_entry(session_key)
                
                # Retry a few times to let token data settle
                for _ in range(3):
                    if isinstance(entry, dict):
                        has_token_data = (
                            isinstance(entry.get("inputTokens"), int)
                            or isinstance(entry.get("outputTokens"), int)
                            or isinstance(entry.get("totalTokens"), int)
                        )
                        if has_token_data:
                            break
                    
                    await asyncio.sleep(0.15)
                    entry = session_manager.get_session_entry(session_key)
                
                if isinstance(entry, dict):
                    input_tokens = entry.get("inputTokens", 0) or 0
                    output_tokens = entry.get("outputTokens", 0) or 0
                    total_tokens = entry.get("totalTokens")
        except Exception as e:
            logger.debug(f"Failed to read token stats: {e}")
    
    io_total = input_tokens + output_tokens
    
    # Calculate runtime
    runtime_ms = None
    if isinstance(started_at, int) and isinstance(ended_at, int):
        runtime_ms = max(0, ended_at - started_at)
    
    # Build stats parts
    parts = [
        f"runtime {format_duration_short(runtime_ms)}",
        f"tokens {format_token_count(io_total)} (in {format_token_count(input_tokens)} / out {format_token_count(output_tokens)})",
    ]
    
    if isinstance(total_tokens, int) and total_tokens > io_total:
        parts.append(f"prompt/cache {format_token_count(total_tokens)}")
    
    return f"Stats: {' • '.join(parts)}"


def build_completion_delivery_message(
    findings: str,
    subagent_name: str,
) -> str:
    """
    Build user-facing completion message.
    
    Mirrors TS buildCompletionDeliveryMessage() lines 48-59
    """
    findings_text = findings.strip()
    has_findings = findings_text and findings_text != "(no output)"
    header = f"✅ Subagent {subagent_name} finished"
    
    if not has_findings:
        return header
    
    return f"{header}\n\n{findings_text}"


def build_announce_reply_instruction(
    *,
    remaining_active_subagent_runs: int,
    requester_is_subagent: bool,
    announce_type: SubagentAnnounceType,
    expects_completion_message: bool = False,
) -> str:
    """
    Build reply instruction for announce message.
    
    Mirrors TS buildAnnounceReplyInstruction() lines 690-707
    """
    if expects_completion_message:
        return (
            f"A completed {announce_type} is ready for user delivery. "
            "Convert the result above into your normal assistant voice and send that user-facing update now. "
            "Keep this internal context private (don't mention system/log/stats/session details or announce type)."
        )
    
    if remaining_active_subagent_runs > 0:
        active_runs_label = "run" if remaining_active_subagent_runs == 1 else "runs"
        return (
            f"There are still {remaining_active_subagent_runs} active subagent {active_runs_label} for this session. "
            "If they are part of the same workflow, wait for the remaining results before sending a user update. "
            "If they are unrelated, respond normally using only the result above."
        )
    
    if requester_is_subagent:
        return (
            "Convert this completion into a concise internal orchestration update for your parent agent in your own words. "
            f"Keep this internal context private (don't mention system/log/stats/session details or announce type). "
            f"If this result is duplicate or no update is needed, reply ONLY: {SILENT_REPLY_TOKEN}."
        )
    
    return (
        f"A completed {announce_type} is ready for user delivery. "
        "Convert the result above into your normal assistant voice and send that user-facing update now. "
        "Keep this internal context private (don't mention system/log/stats/session details or announce type), "
        f"and do not copy the system message verbatim. Reply ONLY: {SILENT_REPLY_TOKEN} if this exact result was already delivered to the user in this same turn."
    )


async def read_latest_subagent_output(
    session_key: str,
    gateway: Any = None,
) -> str | None:
    """
    Read latest output from subagent session.
    
    Mirrors TS readLatestSubagentOutput() lines 164-178
    """
    if not gateway:
        return None
    
    try:
        # Call chat.history to get recent messages
        from openclaw.gateway.api.chat import chat_history
        
        mock_connection = type("MockConnection", (), {"gateway": gateway})()
        result = await chat_history(
            mock_connection,
            {"sessionKey": session_key, "limit": 50},
        )
        
        messages = result.get("messages", [])
        if not isinstance(messages, list):
            return None
        
        # Find last assistant message
        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            if isinstance(msg, dict):
                role = msg.get("role")
                content = msg.get("content")
                
                if role == "assistant":
                    if isinstance(content, str):
                        return content.strip() or None
                    if isinstance(content, list):
                        # Extract text from content array
                        text_parts = []
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                text_parts.append(str(item.get("text", "")))
                            elif isinstance(item, str):
                                text_parts.append(item)
                        result_text = " ".join(text_parts).strip()
                        if result_text:
                            return result_text
    
    except Exception as e:
        logger.debug(f"Failed to read subagent output: {e}")
    
    return None


async def run_subagent_announce_flow(
    *,
    child_session_key: str,
    child_run_id: str,
    requester_session_key: str,
    requester_origin: dict[str, Any] | None,
    requester_display_key: str,
    task: str,
    timeout_ms: int,
    cleanup: Literal["delete", "keep"],
    wait_for_completion: bool = True,
    started_at: int | None = None,
    ended_at: int | None = None,
    label: str | None = None,
    outcome: dict[str, Any] | None = None,
    announce_type: SubagentAnnounceType = "subagent task",
    expects_completion_message: bool = False,
    gateway: Any = None,
) -> bool:
    """
    Run subagent completion announcement flow.
    
    Fully aligned with TS runSubagentAnnounceFlow() from subagent-announce.ts lines 709-990
    
    This function:
    1. Waits for subagent completion (if wait_for_completion=True)
    2. Reads subagent output
    3. Builds announcement message with stats
    4. Delivers to requester (via queue/steer/direct)
    5. Handles cleanup (optional session deletion)
    
    Args:
        child_session_key: Child session key
        child_run_id: Run ID
        requester_session_key: Requester session key
        requester_origin: Origin delivery context
        requester_display_key: Display key for requester
        task: Task description
        timeout_ms: Timeout in milliseconds
        cleanup: Cleanup strategy ("delete" or "keep")
        wait_for_completion: Whether to wait for completion
        started_at: Start timestamp (ms)
        ended_at: End timestamp (ms)
        label: Optional label
        outcome: Outcome data
        announce_type: Type of announcement
        expects_completion_message: Whether requester expects completion message
        gateway: Gateway instance
    
    Returns:
        True if announcement was delivered successfully
    """
    did_announce = False
    should_delete_child_session = cleanup == "delete"
    
    try:
        target_requester_session_key = requester_session_key
        
        # Wait for completion if needed (mirrors TS lines 755-789)
        if wait_for_completion and gateway:
            try:
                from openclaw.gateway.handlers import handle_agent_wait
                
                mock_connection = type("MockConnection", (), {"gateway": gateway})()
                wait_result = await handle_agent_wait(
                    mock_connection,
                    {
                        "runId": child_run_id,
                        "timeoutMs": timeout_ms,
                    },
                )
                
                wait_status = wait_result.get("status")
                if wait_status == "timeout":
                    outcome = {"status": "timeout"}
                elif wait_status == "error":
                    outcome = {"status": "error", "error": wait_result.get("error")}
                elif wait_status == "ok":
                    outcome = {"status": "ok"}
                
                if "startedAt" in wait_result and not started_at:
                    started_at = wait_result["startedAt"]
                if "endedAt" in wait_result and not ended_at:
                    ended_at = wait_result["endedAt"]
            
            except Exception as e:
                logger.warning(f"Failed to wait for subagent completion: {e}")
                outcome = {"status": "unknown"}
        
        # Read subagent output (mirrors TS lines 792-812)
        reply = await read_latest_subagent_output(child_session_key, gateway)
        
        if not reply or not reply.strip():
            reply = "(no output)"
        
        if not outcome:
            outcome = {"status": "unknown"}
        
        # Build status label (mirrors TS lines 832-840)
        status = outcome.get("status", "unknown")
        if status == "ok":
            status_label = "completed successfully"
        elif status == "timeout":
            status_label = "timed out"
        elif status == "error":
            error = outcome.get("error", "unknown error")
            status_label = f"failed: {error}"
        else:
            status_label = "finished with unknown status"
        
        # Resolve agent name and IDs (mirrors TS lines 844-846)
        from openclaw.routing.session_key import resolve_agent_id_from_session_key
        
        task_label = label or task or "task"
        subagent_name = resolve_agent_id_from_session_key(child_session_key) or "subagent"
        
        # Get session ID for logging
        announce_session_id = "unknown"
        if gateway and hasattr(gateway, "session_manager"):
            try:
                entry = gateway.session_manager.get_session_entry(child_session_key)
                if isinstance(entry, dict):
                    announce_session_id = entry.get("sessionId", "unknown")
            except Exception:
                pass
        
        findings = reply or "(no output)"
        
        # Check requester depth (mirrors TS lines 851-889)
        from openclaw.agents.subagent_spawn import get_subagent_depth_from_session_store
        
        requester_depth = get_subagent_depth_from_session_store(
            target_requester_session_key,
            gateway=gateway,
        )
        requester_is_subagent = not expects_completion_message and requester_depth >= 1
        
        # Count remaining active subagent runs (mirrors TS lines 891-900)
        from openclaw.agents.subagent_registry import get_global_registry
        
        registry = get_global_registry()
        remaining_active_runs = 0
        
        try:
            # Count active descendants for target requester
            active_runs = registry.list_runs_for_requester(
                target_requester_session_key,
                active_only=True,
            )
            remaining_active_runs = len(active_runs)
        except Exception as e:
            logger.debug(f"Failed to count active runs: {e}")
        
        # Build announce message (mirrors TS lines 901-924)
        reply_instruction = build_announce_reply_instruction(
            remaining_active_subagent_runs=remaining_active_runs,
            requester_is_subagent=requester_is_subagent,
            announce_type=announce_type,
            expects_completion_message=expects_completion_message,
        )
        
        stats_line = await build_compact_announce_stats_line(
            child_session_key,
            started_at,
            ended_at,
            gateway,
        )
        
        completion_message = build_completion_delivery_message(
            findings,
            subagent_name,
        )
        
        internal_summary_message = "\n".join([
            f"[System Message] [sessionId: {announce_session_id}] A {announce_type} \"{task_label}\" just {status_label}.",
            "",
            "Result:",
            findings,
            "",
            stats_line,
        ])
        
        trigger_message = "\n\n".join([internal_summary_message, reply_instruction])
        
        # Deliver announcement (mirrors TS lines 941-955)
        delivery_result = await _deliver_subagent_announcement(
            requester_session_key=target_requester_session_key,
            trigger_message=trigger_message,
            completion_message=completion_message,
            requester_origin=requester_origin,
            requester_is_subagent=requester_is_subagent,
            expects_completion_message=expects_completion_message,
            gateway=gateway,
        )
        
        did_announce = delivery_result.get("delivered", False)
        
        if not delivery_result.get("delivered") and delivery_result.get("error"):
            logger.error(
                f"Subagent completion direct announce failed for run {child_run_id}: "
                f"{delivery_result['error']}"
            )
    
    except Exception as err:
        logger.error(f"Subagent announce failed: {err}", exc_info=True)
    
    finally:
        # Patch label after all writes complete (mirrors TS lines 966-976)
        if label and gateway:
            try:
                from openclaw.gateway.api.sessions_methods import SessionsPatchMethod
                
                patch_method = SessionsPatchMethod()
                mock_connection = type("MockConnection", (), {"gateway": gateway})()
                
                await patch_method.execute(
                    mock_connection,
                    {"key": child_session_key, "patch": {"label": label}},
                )
            except Exception:
                pass
        
        # Delete child session if requested (mirrors TS lines 977-987)
        if should_delete_child_session and gateway:
            try:
                from openclaw.gateway.api.sessions_methods import SessionsDeleteMethod
                
                delete_method = SessionsDeleteMethod()
                mock_connection = type("MockConnection", (), {"gateway": gateway})()
                
                await delete_method.execute(
                    mock_connection,
                    {"key": child_session_key, "deleteTranscript": True},
                )
            except Exception:
                pass
    
    return did_announce


async def _deliver_subagent_announcement(
    *,
    requester_session_key: str,
    trigger_message: str,
    completion_message: str | None,
    requester_origin: dict[str, Any] | None,
    requester_is_subagent: bool,
    expects_completion_message: bool,
    gateway: Any = None,
) -> dict[str, Any]:
    """
    Deliver announcement to requester session.
    
    Simplified version of TS deliverSubagentAnnouncement.
    
    Returns:
        {"delivered": bool, "path": str, "error": str | None}
    """
    if not gateway:
        return {"delivered": False, "path": "none", "error": "No gateway"}
    
    try:
        # Direct delivery (simplified - mirrors TS sendSubagentAnnounceDirectly)
        from openclaw.gateway.handlers import handle_agent
        
        mock_connection = type("MockConnection", (), {"gateway": gateway})()
        
        agent_params = {
            "message": trigger_message,
            "sessionKey": requester_session_key,
            "deliver": not requester_is_subagent,
        }
        
        # Add origin info for non-subagent requesters
        if not requester_is_subagent and requester_origin:
            if requester_origin.get("channel"):
                agent_params["channel"] = requester_origin["channel"]
            if requester_origin.get("to"):
                agent_params["to"] = requester_origin["to"]
            if requester_origin.get("accountId"):
                agent_params["accountId"] = requester_origin["accountId"]
            if requester_origin.get("threadId"):
                agent_params["threadId"] = str(requester_origin["threadId"])
        
        await handle_agent(mock_connection, agent_params)
        
        return {"delivered": True, "path": "direct"}
    
    except Exception as err:
        return {
            "delivered": False,
            "path": "direct",
            "error": str(err),
        }
