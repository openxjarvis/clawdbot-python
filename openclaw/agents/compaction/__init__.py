"""
Advanced context compaction strategies
"""

from .analyzer import TokenAnalyzer
from .strategy import CompactionManager, CompactionStrategy
from .functions import (
    BASE_CHUNK_RATIO,
    MIN_CHUNK_RATIO,
    SAFETY_MARGIN,
    estimate_messages_tokens,
    split_messages_by_token_share,
    chunk_messages_by_max_tokens,
    compute_adaptive_chunk_ratio,
    is_oversized_for_summary,
    summarize_with_fallback,
    summarize_in_stages,
    prune_history_for_context_share,
    resolve_context_window_tokens,
)

__all__ = [
    "TokenAnalyzer",
    "CompactionManager",
    "CompactionStrategy",
    # TS-aligned functional API
    "BASE_CHUNK_RATIO",
    "MIN_CHUNK_RATIO",
    "SAFETY_MARGIN",
    "estimate_messages_tokens",
    "split_messages_by_token_share",
    "chunk_messages_by_max_tokens",
    "compute_adaptive_chunk_ratio",
    "is_oversized_for_summary",
    "summarize_with_fallback",
    "summarize_in_stages",
    "prune_history_for_context_share",
    "resolve_context_window_tokens",
]
