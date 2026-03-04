"""Hybrid search combining vector and keyword search

Merges results from:
- Vector similarity search
- FTS5 keyword search

Using weighted scoring.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Search result"""
    
    id: str
    text: str
    path: str
    source: str
    score: float
    start_line: int | None = None
    end_line: int | None = None


def merge_hybrid_results(
    vector_results: List[SearchResult],
    keyword_results: List[SearchResult],
    vector_weight: float = 0.7,
    text_weight: float = 0.3,
    min_score: float = 0.0,
) -> List[SearchResult]:
    """
    Merge vector and keyword search results
    
    Uses weighted scoring to combine results:
    - Vector results get vector_weight
    - Keyword results get text_weight
    - Results from both get combined score
    
    Args:
        vector_results: Vector search results
        keyword_results: Keyword search results
        vector_weight: Weight for vector scores (0-1)
        text_weight: Weight for keyword scores (0-1)
        min_score: Minimum score threshold
        
    Returns:
        Merged and sorted results
    """
    # Normalize weights
    total_weight = vector_weight + text_weight
    vector_weight = vector_weight / total_weight
    text_weight = text_weight / total_weight
    
    # Index by chunk ID
    merged: dict[str, SearchResult] = {}
    
    # Add vector results
    for result in vector_results:
        merged[result.id] = result
        # Apply weight
        merged[result.id].score = result.score * vector_weight
    
    # Add keyword results
    for result in keyword_results:
        if result.id in merged:
            # Combine scores
            merged[result.id].score += result.score * text_weight
        else:
            # New result
            merged[result.id] = result
            merged[result.id].score = result.score * text_weight
    
    # Convert to list
    results = list(merged.values())
    
    # Filter by min score
    if min_score > 0:
        results = [r for r in results if r.score >= min_score]
    
    # Sort by score (descending)
    results.sort(key=lambda r: r.score, reverse=True)
    
    logger.debug(
        f"Merged {len(vector_results)} vector + {len(keyword_results)} keyword "
        f"-> {len(results)} hybrid results"
    )
    
    return results


def apply_temporal_decay(
    results: List[SearchResult],
    half_life_days: float = 30.0,
    current_timestamp_ms: int | None = None,
) -> List[SearchResult]:
    """
    Apply temporal decay to search result scores.

    Matches TypeScript memory temporal decay logic:
    - Recent memories score higher
    - Half-life: scores halve every ``half_life_days`` days

    Args:
        results: Search results (each may have an optional `timestamp` attribute).
        half_life_days: Days after which relevance halves.
        current_timestamp_ms: Current time in ms (default: now).

    Returns:
        Results with decay-adjusted scores.
    """
    import math
    import time

    if not results:
        return results

    now_ms = current_timestamp_ms or int(time.time() * 1000)
    half_life_ms = half_life_days * 24 * 3600 * 1000

    for result in results:
        ts_ms = getattr(result, "timestamp_ms", None)
        if ts_ms is None:
            continue  # No timestamp — skip decay
        age_ms = max(0, now_ms - ts_ms)
        decay = math.exp(-math.log(2) * age_ms / half_life_ms)
        result.score *= decay

    return results


MemoryCitationsMode = str  # "none" | "inline" | "footnotes" | "full"


def format_memory_citations(
    results: List[SearchResult],
    mode: MemoryCitationsMode = "inline",
) -> str:
    """
    Format memory search results with citation style.

    Matches TypeScript memoryCitationsMode handling in system prompt builder.

    Modes:
    - "none": Return raw text only, no citations
    - "inline": Each chunk has a [source] suffix
    - "footnotes": Footnotes at the end
    - "full": Full path + content block per result

    Args:
        results: Search results.
        mode: Citation style mode.

    Returns:
        Formatted string for injection into the system prompt.
    """
    if not results:
        return ""

    if mode == "none":
        return "\n".join(r.text for r in results)

    if mode == "full":
        parts = []
        for r in results:
            parts.append(f"**{r.path}** (score={r.score:.2f})")
            parts.append(r.text)
            parts.append("")
        return "\n".join(parts)

    if mode == "footnotes":
        body_parts = []
        footnotes = []
        for i, r in enumerate(results, 1):
            body_parts.append(f"{r.text} [{i}]")
            footnotes.append(f"[{i}] {r.path}")
        return "\n".join(body_parts) + "\n\n" + "\n".join(footnotes)

    # Default: "inline"
    return "\n".join(f"{r.text} [{r.path}]" for r in results)


def apply_mmr(
    results: List[SearchResult],
    limit: int,
    lambda_param: float = 0.7,
) -> List[SearchResult]:
    """Maximal Marginal Relevance (MMR) re-ranking for diversity.

    Mirrors TS ``MemoryIndexManager`` MMR post-hybrid diversity re-ranking.

    After hybrid scoring, MMR iteratively selects the next result that best
    balances relevance (pre-computed ``score``) against redundancy with already
    selected results:

        mmr_score(d) = λ × relevance(d) - (1 - λ) × max_similarity(d, selected)

    Similarity is estimated via token-level Jaccard overlap on the result text,
    which is a reasonable proxy when raw embedding vectors are not available.

    Args:
        results:       Pre-scored candidate results (any order).
        limit:         Maximum number of results to return.
        lambda_param:  Relevance vs diversity trade-off (default 0.7).
                       1.0 = pure relevance ranking, 0.0 = pure diversity.

    Returns:
        Re-ranked list of up to ``limit`` results.
    """
    if not results:
        return results
    limit = max(1, limit)
    if len(results) <= limit:
        return results

    # Tokenise each result text into a frozenset of lower-cased tokens for fast
    # Jaccard similarity computation.
    def _tokenise(text: str) -> frozenset:
        return frozenset(text.lower().split())

    token_sets: list[frozenset] = [_tokenise(r.text) for r in results]

    def _jaccard(a: frozenset, b: frozenset) -> float:
        if not a and not b:
            return 1.0
        union = len(a | b)
        return len(a & b) / union if union > 0 else 0.0

    selected_indices: list[int] = []
    remaining = list(range(len(results)))

    # Seed with the highest-relevance candidate
    best_seed = max(remaining, key=lambda i: results[i].score)
    selected_indices.append(best_seed)
    remaining.remove(best_seed)

    while remaining and len(selected_indices) < limit:
        best_idx: int | None = None
        best_mmr: float = float("-inf")

        for i in remaining:
            rel = results[i].score
            # Maximum similarity to any already-selected result
            max_sim = max(
                _jaccard(token_sets[i], token_sets[j]) for j in selected_indices
            )
            mmr = lambda_param * rel - (1.0 - lambda_param) * max_sim
            if mmr > best_mmr:
                best_mmr = mmr
                best_idx = i

        if best_idx is None:
            break
        selected_indices.append(best_idx)
        remaining.remove(best_idx)

    selected = [results[i] for i in selected_indices]
    logger.debug(
        "MMR re-ranked %d candidates → %d results (λ=%.2f)",
        len(results),
        len(selected),
        lambda_param,
    )
    return selected


def normalize_scores(results: List[SearchResult]) -> List[SearchResult]:
    """
    Normalize scores to 0-1 range
    
    Args:
        results: Search results
        
    Returns:
        Results with normalized scores
    """
    if not results:
        return results
    
    # Find min/max scores
    scores = [r.score for r in results]
    min_score = min(scores)
    max_score = max(scores)
    
    if max_score == min_score:
        # All same score
        for result in results:
            result.score = 1.0
        return results
    
    # Normalize to 0-1
    score_range = max_score - min_score
    
    for result in results:
        result.score = (result.score - min_score) / score_range
    
    return results
