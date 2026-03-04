"""ACP runtime adapter contract test kit — mirrors src/acp/runtime/adapter-contract.testkit.ts

Provides runAcpRuntimeAdapterContract() which can be called in pytest tests
to verify that an AcpRuntime backend implementation satisfies the required
adapter contract.
"""
from __future__ import annotations

import uuid
from typing import Any, AsyncIterator, Callable

from .errors import to_acp_runtime_error
from .types import AcpRuntime, AcpRuntimeEvent


async def run_acp_runtime_adapter_contract(
    create_runtime: Callable[[], Any],
    *,
    agent_id: str | None = None,
    success_prompt: str | None = None,
    error_prompt: str | None = None,
    include_control_checks: bool = True,
    assert_success_events: Callable[[list[AcpRuntimeEvent]], Any] | None = None,
    assert_error_outcome: Callable[[dict[str, Any]], Any] | None = None,
) -> None:
    """
    Run the ACP runtime adapter contract test suite against a given runtime.

    Verifies:
    1. ensureSession() creates a valid handle
    2. runTurn() streams at least one valid event for a success prompt
    3. Optional: getStatus(), setMode(), setConfigOption()
    4. Optional: runTurn() with an error prompt produces error event or raises
    5. cancel() and close() are callable

    Intended for use in pytest with ``pytest.mark.asyncio``.
    """
    runtime: AcpRuntime = await create_runtime() if callable(create_runtime) else create_runtime
    agent = agent_id or "codex"
    session_key = f"agent:{agent}:acp:contract-{uuid.uuid4().hex}"

    handle = await runtime.ensure_session({
        "sessionKey": session_key,
        "agent": agent,
        "mode": "persistent",
    })

    assert handle.get("sessionKey") == session_key, "handle.sessionKey must match input"
    assert handle.get("backend", "").strip(), "handle.backend must be non-empty"
    assert handle.get("runtimeSessionName", "").strip(), "handle.runtimeSessionName must be non-empty"

    # --- Success turn ---
    success_events: list[AcpRuntimeEvent] = []
    async for event in runtime.run_turn({
        "handle": handle,
        "text": success_prompt or "contract-success",
        "mode": "prompt",
        "requestId": f"contract-success-{uuid.uuid4().hex}",
    }):
        success_events.append(event)

    has_valid_event = any(
        e.get("type") in ("done", "text_delta", "status", "tool_call")
        for e in success_events
    )
    assert has_valid_event, (
        "Success turn must yield at least one done/text_delta/status/tool_call event"
    )
    if assert_success_events:
        await assert_success_events(success_events) if callable(assert_success_events) else None

    # --- Optional control checks ---
    if include_control_checks:
        if hasattr(runtime, "get_status") and callable(runtime.get_status):
            status = await runtime.get_status({"handle": handle})
            assert isinstance(status, dict), "getStatus must return a dict"

        if hasattr(runtime, "set_mode") and callable(runtime.set_mode):
            await runtime.set_mode({"handle": handle, "mode": "contract"})

        if hasattr(runtime, "set_config_option") and callable(runtime.set_config_option):
            await runtime.set_config_option({
                "handle": handle,
                "key": "contract_key",
                "value": "contract_value",
            })

    # --- Error turn (optional) ---
    error_thrown: Any = None
    error_events: list[AcpRuntimeEvent] = []
    if error_prompt and error_prompt.strip():
        try:
            async for event in runtime.run_turn({
                "handle": handle,
                "text": error_prompt.strip(),
                "mode": "prompt",
                "requestId": f"contract-error-{uuid.uuid4().hex}",
            }):
                error_events.append(event)
        except Exception as exc:
            error_thrown = exc

        saw_error_event = any(e.get("type") == "error" for e in error_events)
        assert bool(error_thrown) or saw_error_event, (
            "Error turn must raise an exception or emit an error event"
        )
        if error_thrown:
            acp_error = to_acp_runtime_error(
                error_thrown,
                fallback_code="ACP_TURN_FAILED",
                fallback_message="ACP runtime contract expected an error turn failure.",
            )
            assert len(acp_error.code) > 0
            assert len(str(acp_error)) > 0

    if assert_error_outcome:
        result = assert_error_outcome({"events": error_events, "thrown": error_thrown})
        if hasattr(result, "__await__"):
            await result

    # --- Teardown ---
    await runtime.cancel({"handle": handle, "reason": "contract-cancel"})
    await runtime.close({"handle": handle, "reason": "contract-close"})
