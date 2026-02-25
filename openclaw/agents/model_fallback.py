"""Model fallback execution loop.

Aligned with TypeScript openclaw/src/agents/model-fallback.ts.
Iterates through a prioritised list of model candidates, retrying on
retryable FailoverErrors and respecting per-provider auth profile cooldowns.
"""
from __future__ import annotations

import asyncio
import time
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from .defaults import DEFAULT_MODEL, DEFAULT_PROVIDER
from .failover.errors import (
    FailoverReason,
    coerce_to_failover_error,
    describe_failover_error,
    is_failover_error,
    is_likely_context_overflow_error,
    is_timeout_error,
)
from .model_selection import (
    build_configured_allowlist_keys,
    build_model_alias_index,
    model_key,
    normalize_model_ref,
    resolve_configured_model_ref,
    resolve_model_ref_from_string,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Internal data types
# ---------------------------------------------------------------------------

@dataclass
class ModelCandidate:
    provider: str
    model: str


@dataclass
class FallbackAttempt:
    provider: str
    model: str
    error: str
    reason: FailoverReason | None = None
    status: int | None = None
    code: str | None = None


@dataclass
class ModelFallbackRunResult:
    result: Any
    provider: str
    model: str
    attempts: list[FallbackAttempt] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Probe throttle — mirrors TS _probeThrottleInternals
# ---------------------------------------------------------------------------

_last_probe_attempt: dict[str, float] = {}
_MIN_PROBE_INTERVAL_MS: float = 30_000  # 30 s between probes per key
_PROBE_MARGIN_MS: float = 2 * 60 * 1000  # 2 min
_PROBE_SCOPE_DELIMITER = "::"


def _resolve_probe_throttle_key(provider: str, agent_dir: str | None = None) -> str:
    scope = (agent_dir or "").strip()
    return f"{scope}{_PROBE_SCOPE_DELIMITER}{provider}" if scope else provider


# Exposed for unit tests (mirrors TS _probeThrottleInternals)
_probe_throttle_internals: dict[str, Any] = {
    "last_probe_attempt": _last_probe_attempt,
    "MIN_PROBE_INTERVAL_MS": _MIN_PROBE_INTERVAL_MS,
    "PROBE_MARGIN_MS": _PROBE_MARGIN_MS,
    "resolve_probe_throttle_key": _resolve_probe_throttle_key,
}


# ---------------------------------------------------------------------------
# Auth profile cooldown helpers (thin wrappers around RotationManager / ProfileStore)
# ---------------------------------------------------------------------------

def _get_profile_store(agent_dir: str | None) -> Any | None:
    """Return a ProfileStore if one can be loaded, else None."""
    try:
        from openclaw.agents.auth.profile import ProfileStore
        from openclaw.config.auth_profiles import load_auth_profile_store

        raw = load_auth_profile_store()
        store = ProfileStore()
        for profile_data in (raw.get("profiles") or {}).values():
            from openclaw.agents.auth.profile import AuthProfile
            try:
                profile = AuthProfile.from_dict(profile_data)
                store.add_profile(profile)
            except Exception:
                pass
        return store
    except Exception:
        return None


def _is_profile_in_cooldown(store: Any, profile_id: str) -> bool:
    profile = store.get_profile(profile_id) if store else None
    if profile is None:
        return False
    return not profile.is_available()


def _get_soonest_cooldown_expiry(store: Any, profile_ids: list[str]) -> float | None:
    """Return the earliest cooldown expiry timestamp (epoch ms), or None."""
    if not store:
        return None
    earliest: float | None = None
    for pid in profile_ids:
        profile = store.get_profile(pid)
        if profile and profile.cooldown_until is not None:
            ts = profile.cooldown_until.timestamp() * 1000
            if earliest is None or ts < earliest:
                earliest = ts
    return earliest


def _resolve_auth_profile_order(
    cfg: Any,
    store: Any,
    provider: str,
) -> list[str]:
    """Return ordered list of profile IDs for *provider*."""
    if not store:
        return []
    try:
        profiles = store.list_profiles(provider)
        return [p.id for p in profiles]
    except Exception:
        return []


def _should_probe_primary_during_cooldown(
    *,
    is_primary: bool,
    has_fallback_candidates: bool,
    now_ms: float,
    throttle_key: str,
    store: Any,
    profile_ids: list[str],
) -> bool:
    if not is_primary or not has_fallback_candidates:
        return False
    last_probe = _last_probe_attempt.get(throttle_key, 0.0)
    if now_ms - last_probe < _MIN_PROBE_INTERVAL_MS:
        return False
    soonest = _get_soonest_cooldown_expiry(store, profile_ids)
    if soonest is None or not (soonest == soonest):  # None or NaN
        return True
    return now_ms >= soonest - _PROBE_MARGIN_MS


# ---------------------------------------------------------------------------
# Candidate collection
# ---------------------------------------------------------------------------

def _create_model_candidate_collector(
    allowlist: set[str] | None,
) -> tuple[list[ModelCandidate], Callable]:
    seen: set[str] = set()
    candidates: list[ModelCandidate] = []

    def add_candidate(candidate: ModelCandidate, enforce_allowlist: bool) -> None:
        if not candidate.provider or not candidate.model:
            return
        key = model_key(candidate.provider, candidate.model)
        if key in seen:
            return
        if enforce_allowlist and allowlist is not None and key not in allowlist:
            return
        seen.add(key)
        candidates.append(candidate)

    return candidates, add_candidate


def resolve_fallback_candidates(
    cfg: Any,
    provider: str,
    model: str,
    fallbacks_override: list[str] | None = None,
) -> list[ModelCandidate]:
    """Build ordered list of ModelCandidate from primary + configured fallbacks.

    Mirrors TS resolveFallbackCandidates().
    """
    primary_ref = resolve_configured_model_ref(cfg) if cfg else None
    default_provider = primary_ref.provider if primary_ref else DEFAULT_PROVIDER
    default_model = primary_ref.model if primary_ref else DEFAULT_MODEL

    provider_raw = (provider or "").strip() or default_provider
    model_raw = (model or "").strip() or default_model
    normalized_primary = normalize_model_ref(provider_raw, model_raw)

    alias_index = build_model_alias_index(cfg or {}, default_provider)
    allowlist = build_configured_allowlist_keys(cfg, default_provider)

    candidates, add_candidate = _create_model_candidate_collector(allowlist)
    add_candidate(ModelCandidate(normalized_primary.provider, normalized_primary.model), False)

    # Determine fallback list
    if fallbacks_override is not None:
        model_fallbacks = fallbacks_override
    else:
        model_fallbacks = []
        if isinstance(cfg, dict):
            agents_section = cfg.get("agents") or {}
            if isinstance(agents_section, dict):
                defaults = agents_section.get("defaults") or {}
                if isinstance(defaults, dict):
                    model_cfg = defaults.get("model")
                    if isinstance(model_cfg, dict):
                        model_fallbacks = list(model_cfg.get("fallbacks") or [])

    for raw in model_fallbacks:
        resolved = resolve_model_ref_from_string(str(raw or ""), default_provider, alias_index)
        if not resolved:
            continue
        ref = resolved["ref"]
        add_candidate(ModelCandidate(ref.provider, ref.model), True)

    # If no explicit override, also add the config-default as a final fallback
    if fallbacks_override is None and primary_ref and primary_ref.provider and primary_ref.model:
        add_candidate(ModelCandidate(primary_ref.provider, primary_ref.model), False)

    return candidates


def resolve_image_fallback_candidates(
    cfg: Any,
    default_provider: str = DEFAULT_PROVIDER,
    model_override: str | None = None,
) -> list[ModelCandidate]:
    """Build image model fallback candidates.

    Mirrors TS resolveImageFallbackCandidates().
    """
    alias_index = build_model_alias_index(cfg or {}, default_provider)
    allowlist = build_configured_allowlist_keys(cfg, default_provider)
    candidates, add_candidate = _create_model_candidate_collector(allowlist)

    def add_raw(raw: str, enforce_allowlist: bool) -> None:
        resolved = resolve_model_ref_from_string(str(raw or ""), default_provider, alias_index)
        if not resolved:
            return
        ref = resolved["ref"]
        add_candidate(ModelCandidate(ref.provider, ref.model), enforce_allowlist)

    if model_override and model_override.strip():
        add_raw(model_override, False)
    else:
        image_model = None
        if isinstance(cfg, dict):
            agents_section = cfg.get("agents") or {}
            if isinstance(agents_section, dict):
                defaults = agents_section.get("defaults") or {}
                if isinstance(defaults, dict):
                    image_model = defaults.get("imageModel")
        primary: str | None = None
        if isinstance(image_model, str):
            primary = image_model.strip() or None
        elif isinstance(image_model, dict):
            p = image_model.get("primary")
            if isinstance(p, str):
                primary = p.strip() or None
        if primary:
            add_raw(primary, False)

    # Image fallbacks
    image_fallbacks: list[str] = []
    if isinstance(cfg, dict):
        agents_section = cfg.get("agents") or {}
        if isinstance(agents_section, dict):
            defaults = agents_section.get("defaults") or {}
            if isinstance(defaults, dict):
                image_model = defaults.get("imageModel")
                if isinstance(image_model, dict):
                    image_fallbacks = list(image_model.get("fallbacks") or [])

    for raw in image_fallbacks:
        add_raw(raw, True)

    return candidates


# ---------------------------------------------------------------------------
# Abort detection
# ---------------------------------------------------------------------------

def _is_fallback_abort_error(err: Any) -> bool:
    if not err or not isinstance(err, Exception):
        return False
    if is_failover_error(err):
        return False
    return type(err).__name__ == "AbortError"


def _should_rethrow_abort(err: Any) -> bool:
    return _is_fallback_abort_error(err) and not is_timeout_error(err)


# ---------------------------------------------------------------------------
# Main fallback execution
# ---------------------------------------------------------------------------

async def run_with_model_fallback(
    cfg: Any,
    provider: str,
    model: str,
    run_fn: Callable[[str, str], Awaitable[Any]],
    agent_dir: str | None = None,
    fallbacks_override: list[str] | None = None,
    on_error: Callable[[dict[str, Any]], Any] | None = None,
) -> ModelFallbackRunResult:
    """Execute *run_fn* with automatic failover across model candidates.

    Mirrors TS runWithModelFallback().
    - Iterates over candidates in order.
    - Skips providers whose auth profiles are all in cooldown (unless probing).
    - Rethrows AbortError (non-timeout) and context-overflow errors immediately.
    - Returns ModelFallbackRunResult with result, final provider/model, and attempts.
    """
    candidates = resolve_fallback_candidates(cfg, provider, model, fallbacks_override)
    store = _get_profile_store(agent_dir) if cfg else None
    attempts: list[FallbackAttempt] = []
    last_error: BaseException | None = None
    has_fallback_candidates = len(candidates) > 1

    for i, candidate in enumerate(candidates):
        if store:
            profile_ids = _resolve_auth_profile_order(cfg, store, candidate.provider)
            is_any_available = any(
                not _is_profile_in_cooldown(store, pid) for pid in profile_ids
            )
            if profile_ids and not is_any_available:
                now_ms = time.time() * 1000
                throttle_key = _resolve_probe_throttle_key(candidate.provider, agent_dir)
                should_probe = _should_probe_primary_during_cooldown(
                    is_primary=(i == 0),
                    has_fallback_candidates=has_fallback_candidates,
                    now_ms=now_ms,
                    throttle_key=throttle_key,
                    store=store,
                    profile_ids=profile_ids,
                )
                if not should_probe:
                    attempts.append(FallbackAttempt(
                        provider=candidate.provider,
                        model=candidate.model,
                        error=(
                            f"Provider {candidate.provider} is in cooldown "
                            "(all profiles unavailable)"
                        ),
                        reason=FailoverReason.RATE_LIMIT,
                    ))
                    continue
                _last_probe_attempt[throttle_key] = now_ms

        try:
            result = await run_fn(candidate.provider, candidate.model)
            return ModelFallbackRunResult(
                result=result,
                provider=candidate.provider,
                model=candidate.model,
                attempts=attempts,
            )
        except Exception as err:
            if _should_rethrow_abort(err):
                raise
            err_msg = str(err)
            if is_likely_context_overflow_error(err_msg):
                raise
            normalized = (
                coerce_to_failover_error(err, {
                    "provider": candidate.provider,
                    "model": candidate.model,
                })
                or err
            )
            if not is_failover_error(normalized):
                raise
            last_error = normalized
            described = describe_failover_error(normalized)
            attempts.append(FallbackAttempt(
                provider=candidate.provider,
                model=candidate.model,
                error=described["message"],
                reason=described.get("reason"),
                status=described.get("status"),
                code=described.get("code"),
            ))
            if on_error:
                result = on_error({
                    "provider": candidate.provider,
                    "model": candidate.model,
                    "error": normalized,
                    "attempt": i + 1,
                    "total": len(candidates),
                })
                if asyncio.iscoroutine(result):
                    await result

    if len(attempts) <= 1 and last_error:
        raise last_error

    summary = (
        " | ".join(
            f"{a.provider}/{a.model}: {a.error}"
            + (f" ({a.reason})" if a.reason else "")
            for a in attempts
        )
        if attempts else "unknown"
    )
    raise RuntimeError(f"All models failed ({len(attempts) or len(candidates)}): {summary}")


async def run_with_image_model_fallback(
    cfg: Any,
    model_override: str | None = None,
    run_fn: Callable[[str, str], Awaitable[Any]] | None = None,
    on_error: Callable[[dict[str, Any]], Any] | None = None,
) -> ModelFallbackRunResult:
    """Execute *run_fn* with image-model fallover.

    Mirrors TS runWithImageModelFallback().
    Simpler than the primary loop — no cooldown checks.
    """
    if run_fn is None:
        raise ValueError("run_fn is required")

    candidates = resolve_image_fallback_candidates(cfg, DEFAULT_PROVIDER, model_override)
    if not candidates:
        raise RuntimeError(
            "No image model configured. Set agents.defaults.imageModel.primary "
            "or agents.defaults.imageModel.fallbacks."
        )

    attempts: list[FallbackAttempt] = []
    last_error: BaseException | None = None

    for i, candidate in enumerate(candidates):
        try:
            result = await run_fn(candidate.provider, candidate.model)
            return ModelFallbackRunResult(
                result=result,
                provider=candidate.provider,
                model=candidate.model,
                attempts=attempts,
            )
        except Exception as err:
            if _should_rethrow_abort(err):
                raise
            last_error = err
            attempts.append(FallbackAttempt(
                provider=candidate.provider,
                model=candidate.model,
                error=str(err),
            ))
            if on_error:
                result_cb = on_error({
                    "provider": candidate.provider,
                    "model": candidate.model,
                    "error": err,
                    "attempt": i + 1,
                    "total": len(candidates),
                })
                if asyncio.iscoroutine(result_cb):
                    await result_cb

    if len(attempts) <= 1 and last_error:
        raise last_error

    summary = (
        " | ".join(f"{a.provider}/{a.model}: {a.error}" for a in attempts)
        if attempts else "unknown"
    )
    raise RuntimeError(
        f"All image models failed ({len(attempts) or len(candidates)}): {summary}"
    )


__all__ = [
    "ModelCandidate",
    "FallbackAttempt",
    "ModelFallbackRunResult",
    "resolve_fallback_candidates",
    "resolve_image_fallback_candidates",
    "run_with_model_fallback",
    "run_with_image_model_fallback",
    "_probe_throttle_internals",
]
