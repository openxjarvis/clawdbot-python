"""ACP runtime backend registry — mirrors src/acp/runtime/registry.ts

Global singleton registry for ACP runtime backends (e.g. acpx plugin).
Uses a module-level dict as the single process-wide store, equivalent to
the TS globalThis Symbol-keyed singleton.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .errors import AcpRuntimeError
from .types import AcpRuntime


@dataclass
class AcpRuntimeBackend:
    id: str
    runtime: AcpRuntime
    healthy: Callable[[], bool] | None = None


# Process-wide registry (equiv. of globalThis[Symbol.for("openclaw.acpRuntimeRegistryState")])
_BACKENDS_BY_ID: dict[str, AcpRuntimeBackend] = {}


def _normalize_backend_id(backend_id: str | None) -> str:
    if not backend_id:
        return ""
    return backend_id.strip().lower()


def _is_backend_healthy(backend: AcpRuntimeBackend) -> bool:
    if backend.healthy is None:
        return True
    try:
        return bool(backend.healthy())
    except Exception:
        return False


def register_acp_runtime_backend(backend: AcpRuntimeBackend) -> None:
    """Register an ACP runtime backend in the global registry."""
    normalized = _normalize_backend_id(backend.id)
    if not normalized:
        raise ValueError("ACP runtime backend id is required")
    if backend.runtime is None:
        raise ValueError(f'ACP runtime backend "{normalized}" is missing runtime implementation')
    _BACKENDS_BY_ID[normalized] = AcpRuntimeBackend(
        id=normalized,
        runtime=backend.runtime,
        healthy=backend.healthy,
    )


def unregister_acp_runtime_backend(backend_id: str) -> None:
    """Remove a backend from the global registry."""
    normalized = _normalize_backend_id(backend_id)
    if normalized:
        _BACKENDS_BY_ID.pop(normalized, None)


def get_acp_runtime_backend(backend_id: str | None = None) -> AcpRuntimeBackend | None:
    """
    Look up a backend by id.  If no id is given, return the first healthy
    registered backend (or the first backend if none are healthy).
    """
    normalized = _normalize_backend_id(backend_id)
    if normalized:
        return _BACKENDS_BY_ID.get(normalized)
    if not _BACKENDS_BY_ID:
        return None
    for backend in _BACKENDS_BY_ID.values():
        if _is_backend_healthy(backend):
            return backend
    return next(iter(_BACKENDS_BY_ID.values()), None)


def require_acp_runtime_backend(backend_id: str | None = None) -> AcpRuntimeBackend:
    """
    Return the backend or raise AcpRuntimeError if unavailable.
    """
    normalized = _normalize_backend_id(backend_id)
    backend = get_acp_runtime_backend(normalized or None)
    if not backend:
        raise AcpRuntimeError(
            "ACP_BACKEND_MISSING",
            "ACP runtime backend is not configured. Install and enable the acpx runtime plugin.",
        )
    if not _is_backend_healthy(backend):
        raise AcpRuntimeError(
            "ACP_BACKEND_UNAVAILABLE",
            "ACP runtime backend is currently unavailable. Try again in a moment.",
        )
    if normalized and backend.id != normalized:
        raise AcpRuntimeError(
            "ACP_BACKEND_MISSING",
            f'ACP runtime backend "{normalized}" is not registered.',
        )
    return backend


# Test helpers
def _reset_acp_runtime_backends_for_tests() -> None:
    _BACKENDS_BY_ID.clear()
