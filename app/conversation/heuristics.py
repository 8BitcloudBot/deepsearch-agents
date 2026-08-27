"""Shared lightweight helpers for the conversation product.

Single source of truth so turn.py and runtime.py stop duplicating the same
logic; B7 later demoted the deep-request predicate to a fallback behind
planner output.
"""

from __future__ import annotations

_DEEP_REQUEST_MARKERS = ("深入", "详细", "全面分析", "深度", "完整分析")


def is_deep_request(question: str) -> bool:
    folded = question.casefold()
    return any(marker in folded for marker in _DEEP_REQUEST_MARKERS)


def rank_decay_scores(count: int) -> list[float]:
    """Position-based decay for rank-scaled sources (no per-call semantics)."""
    return [1 / (index + 1) for index in range(count)]
