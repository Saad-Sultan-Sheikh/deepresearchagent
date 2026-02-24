"""Confidence scoring functions for extracted facts."""

from __future__ import annotations

from src.models.report import ConfidenceScore


# Base scores by source count
_BASE_SCORES = {1: 0.40, 2: 0.60}
_BASE_3_PLUS = 0.75

# Modifiers
_MOD_AUTHORITATIVE = +0.15
_MOD_SOCIAL_ONLY = -0.10
_MOD_CONTRADICTS_SEED = -0.20
_MOD_CORROBORATES_SEED = +0.10
_MOD_CROSS_SOURCE_CONFLICT = -0.25

# Hard caps
_MIN_SCORE = 0.05
_MAX_SCORE = 0.95


def compute_confidence(
    fact: str,
    source_count: int,
    authoritative_source: bool = False,
    social_only: bool = False,
    contradicts_seed: bool = False,
    corroborates_seed: bool = False,
    cross_source_conflict: bool = False,
    rationale: str = "",
) -> ConfidenceScore:
    """Compute a confidence score for a single fact."""
    if source_count <= 0:
        base = 0.05
    elif source_count == 1:
        base = _BASE_SCORES[1]
    elif source_count == 2:
        base = _BASE_SCORES[2]
    else:
        base = _BASE_3_PLUS

    modifier = 0.0
    if authoritative_source:
        modifier += _MOD_AUTHORITATIVE
    if social_only:
        modifier += _MOD_SOCIAL_ONLY
    if contradicts_seed:
        modifier += _MOD_CONTRADICTS_SEED
    if corroborates_seed:
        modifier += _MOD_CORROBORATES_SEED
    if cross_source_conflict:
        modifier += _MOD_CROSS_SOURCE_CONFLICT

    raw_score = base + modifier
    score = max(_MIN_SCORE, min(_MAX_SCORE, raw_score))

    return ConfidenceScore(
        fact=fact,
        score=round(score, 4),
        source_count=source_count,
        authoritative_source=authoritative_source,
        social_only=social_only,
        contradicts_seed=contradicts_seed,
        corroborates_seed=corroborates_seed,
        cross_source_conflict=cross_source_conflict,
        rationale=rationale or _auto_rationale(
            base, modifier, authoritative_source, social_only,
            contradicts_seed, corroborates_seed, cross_source_conflict,
        ),
    )


def _auto_rationale(
    base: float,
    modifier: float,
    authoritative: bool,
    social_only: bool,
    contradicts: bool,
    corroborates: bool,
    conflict: bool,
) -> str:
    parts = [f"base={base:.2f}"]
    if authoritative:
        parts.append("authoritative +0.15")
    if social_only:
        parts.append("social-only -0.10")
    if contradicts:
        parts.append("contradicts-seed -0.20")
    if corroborates:
        parts.append("corroborates-seed +0.10")
    if conflict:
        parts.append("cross-source-conflict -0.25")
    parts.append(f"total modifier={modifier:+.2f}")
    return "; ".join(parts)


def aggregate_confidence(scores: list[float]) -> float:
    """Aggregate multiple confidence scores for a composite finding."""
    if not scores:
        return _MIN_SCORE
    avg = sum(scores) / len(scores)
    return max(_MIN_SCORE, min(_MAX_SCORE, avg))
