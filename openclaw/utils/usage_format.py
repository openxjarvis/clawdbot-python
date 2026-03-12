"""Usage cost estimation and formatting utilities.

Mirrors TypeScript ``src/utils/usage-format.ts``.

Provides:
- ``estimate_usage_cost`` — compute estimated USD cost from token usage
- ``resolve_model_cost_config`` — look up per-token cost from config
- ``format_token_count`` — human-readable token count (1k, 1.2m, ...)
- ``format_usd`` — human-readable USD amount
"""
from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

class ModelCostConfig:
    """Per-token cost configuration for a model."""

    def __init__(
        self,
        input: float = 0.0,
        output: float = 0.0,
        cache_read: float = 0.0,
        cache_write: float = 0.0,
    ) -> None:
        self.input = input
        self.output = output
        self.cache_read = cache_read
        self.cache_write = cache_write


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def format_token_count(value: int | float | None) -> str:
    """Format a token count for display.

    Mirrors TS ``formatTokenCount``.
    """
    if value is None or not isinstance(value, (int, float)):
        return "0"
    safe = max(0, int(value))
    if safe >= 1_000_000:
        return f"{safe / 1_000_000:.1f}m"
    if safe >= 10_000:
        return f"{safe / 1_000:.0f}k"
    if safe >= 1_000:
        return f"{safe / 1_000:.1f}k"
    return str(safe)


def format_usd(value: float | None) -> str | None:
    """Format a USD amount for display.

    Mirrors TS ``formatUsd``.
    """
    if value is None or not isinstance(value, (int, float)):
        return None
    if value >= 0.01:
        return f"${value:.2f}"
    return f"${value:.4f}"


# ---------------------------------------------------------------------------
# Cost resolution
# ---------------------------------------------------------------------------

def resolve_model_cost_config(
    *,
    provider: str | None = None,
    model: str | None = None,
    config: dict[str, Any] | None = None,
) -> ModelCostConfig | None:
    """Look up per-token cost config for a provider/model pair.

    Mirrors TS ``resolveModelCostConfig``.

    Config structure expected under ``config["models"]["providers"]``:
    ```json
    {
      "<provider>": {
        "models": [
          {
            "id": "<model-id>",
            "cost": {"input": 3.0, "output": 15.0, "cacheRead": 0.3, "cacheWrite": 3.75}
          }
        ]
      }
    }
    ```
    Cost values are per-million-tokens in USD.
    """
    if not provider or not model or not config:
        return None
    try:
        providers = (config.get("models") or {}).get("providers") or {}
        provider_entry = providers.get(provider) or {}
        models_list = provider_entry.get("models") or []
        for m in models_list:
            if not isinstance(m, dict):
                continue
            if m.get("id") == model:
                cost_raw = m.get("cost")
                if not isinstance(cost_raw, dict):
                    return None
                return ModelCostConfig(
                    input=float(cost_raw.get("input") or 0),
                    output=float(cost_raw.get("output") or 0),
                    cache_read=float(cost_raw.get("cacheRead") or cost_raw.get("cache_read") or 0),
                    cache_write=float(cost_raw.get("cacheWrite") or cost_raw.get("cache_write") or 0),
                )
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------

def estimate_usage_cost(
    *,
    usage: dict[str, Any] | None = None,
    cost: ModelCostConfig | None = None,
) -> float | None:
    """Estimate USD cost from token usage and per-token cost config.

    Mirrors TS ``estimateUsageCost``.

    Args:
        usage: Token usage dict with keys ``input``, ``output``,
               ``cacheRead``/``cache_read``, ``cacheWrite``/``cache_write``.
        cost: Per-token cost config (from ``resolve_model_cost_config``).

    Returns:
        Estimated cost in USD, or ``None`` if usage/cost are unavailable.
    """
    if not usage or not cost:
        return None

    def _to_num(val: Any) -> float:
        if isinstance(val, (int, float)) and val == val:  # not NaN
            return float(max(0, val))
        return 0.0

    input_tokens = _to_num(usage.get("input"))
    output_tokens = _to_num(usage.get("output"))
    cache_read = _to_num(usage.get("cacheRead") or usage.get("cache_read"))
    cache_write = _to_num(usage.get("cacheWrite") or usage.get("cache_write"))

    total = (
        input_tokens * cost.input
        + output_tokens * cost.output
        + cache_read * cost.cache_read
        + cache_write * cost.cache_write
    )

    if not isinstance(total, float) or total != total:  # NaN guard
        return None

    # Cost values are per-million-tokens, so divide by 1,000,000
    return total / 1_000_000


def format_response_usage_line(
    *,
    usage: dict[str, Any] | None = None,
    show_cost: bool = False,
    cost_config: ModelCostConfig | None = None,
) -> str | None:
    """Format a token-usage summary line for appending to verbose replies.

    Mirrors TS ``formatResponseUsageLine`` from ``agent-runner-utils.ts``.
    Returns a string like ``"Usage: 1.2k in / 300 out · est $0.0021"``
    or ``None`` when usage data is unavailable.

    Args:
        usage: Token usage dict with ``input`` and ``output`` keys.
        show_cost: When True, append estimated cost using ``cost_config``.
        cost_config: Per-token cost configuration for cost estimation.
    """
    if not usage:
        return None

    input_tokens = usage.get("input")
    output_tokens = usage.get("output")

    if input_tokens is None and output_tokens is None:
        return None

    input_label = format_token_count(input_tokens) if input_tokens is not None else "?"
    output_label = format_token_count(output_tokens) if output_tokens is not None else "?"

    cost_label: str | None = None
    if show_cost and isinstance(input_tokens, (int, float)) and isinstance(output_tokens, (int, float)):
        cost = estimate_usage_cost(usage=usage, cost=cost_config)
        cost_label = format_usd(cost)

    suffix = f" · est {cost_label}" if cost_label else ""
    return f"Usage: {input_label} in / {output_label} out{suffix}"


__all__ = [
    "ModelCostConfig",
    "estimate_usage_cost",
    "resolve_model_cost_config",
    "format_token_count",
    "format_usd",
    "format_response_usage_line",
]
