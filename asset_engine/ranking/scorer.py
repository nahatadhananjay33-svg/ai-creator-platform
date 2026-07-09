"""Deterministic candidate ranking (Phase C9).

Scores each :class:`AssetCandidate` against an :class:`AssetQuery` with a fixed,
weighted sum of interpretable components — NO model, NO embeddings, NO
randomness. The same ``(candidates, query, weights)`` always yields the same
ranking, and ties break on ``candidate_id`` so the order is total and stable.

Components (each normalised to ``[0, 1]``):

- **type** — exact kind (1.0), same family / image-like (0.5), cross-family (0.0)
- **aspect** — closeness of the candidate's aspect ratio to the slot region's
- **duration** — for video, whether the clip is long enough for the slot
- **tags** — fraction of the query's tags the candidate carries (tag overlap)
- **resolution** — whether the candidate has enough pixels for the region

The weighted total is what the resolver selects the argmax of.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from asset_engine.catalog.types import AssetCandidate, AssetQuery


@dataclass(frozen=True)
class RankWeights:
    """Relative importance of each scoring component (non-negative)."""

    type: float = 3.0
    aspect: float = 1.5
    duration: float = 1.0
    tags: float = 2.0
    resolution: float = 1.0

    @property
    def total(self) -> float:
        return self.type + self.aspect + self.duration + self.tags + self.resolution

    @classmethod
    def from_mapping(cls, m: dict[str, Any] | None) -> "RankWeights":
        m = m or {}
        d = cls()
        return cls(type=m.get("type", d.type), aspect=m.get("aspect", d.aspect),
                   duration=m.get("duration", d.duration), tags=m.get("tags", d.tags),
                   resolution=m.get("resolution", d.resolution))


@dataclass(frozen=True)
class ScoreBreakdown:
    """Per-component scores (0..1) plus the weighted total — for transparency."""

    type: float
    aspect: float
    duration: float
    tags: float
    resolution: float
    total: float


@dataclass(frozen=True)
class RankedCandidate:
    """A candidate with its score breakdown and final position (0 = best)."""

    candidate: AssetCandidate
    score: float
    breakdown: ScoreBreakdown
    rank: int = 0


# --------------------------------------------------------------- components
def type_score(candidate: AssetCandidate, query: AssetQuery) -> float:
    """1.0 exact kind, 0.5 same family (e.g. a photo for a chart slot), 0.0 across
    the still/video divide (a still can never satisfy a video slot)."""
    if candidate.kind == query.kind:
        return 1.0
    return 0.5 if candidate.family == query.family else 0.0


def aspect_score(candidate: AssetCandidate, query: AssetQuery) -> float:
    """Closeness of aspect ratios; neutral (1.0) when either is unknown."""
    if query.target_aspect <= 0 or candidate.aspect_ratio <= 0:
        return 1.0
    rel = abs(candidate.aspect_ratio - query.target_aspect) / query.target_aspect
    return max(0.0, 1.0 - rel)


def duration_score(candidate: AssetCandidate, query: AssetQuery) -> float:
    """For video: 1.0 if the clip covers the slot, proportional if short. Stills
    (and non-video queries) always satisfy duration (1.0)."""
    if query.family != "video" or query.target_duration_s <= 0:
        return 1.0
    if candidate.duration_s <= 0:
        return 0.5                                # unknown length — neither reward nor reject
    if candidate.duration_s >= query.target_duration_s:
        return 1.0
    return candidate.duration_s / query.target_duration_s


def tag_score(candidate: AssetCandidate, query: AssetQuery) -> float:
    """Fraction of the query's tags the candidate carries (0 when none requested,
    so the component stays neutral across candidates)."""
    if not query.tags:
        return 0.0
    q = set(query.tags)
    overlap = q & set(candidate.tags)
    return len(overlap) / len(q)


def resolution_score(candidate: AssetCandidate, query: AssetQuery) -> float:
    """1.0 when the candidate has at least the region's pixels, proportional
    below; neutral (1.0) when either resolution is unknown."""
    if query.min_pixels <= 0 or candidate.pixels <= 0:
        return 1.0
    return min(1.0, candidate.pixels / query.min_pixels)


# ------------------------------------------------------------------ scoring
def score_candidate(candidate: AssetCandidate, query: AssetQuery,
                    weights: RankWeights | None = None) -> RankedCandidate:
    """Score one candidate against the query (rank filled by :func:`rank_candidates`)."""
    w = weights or RankWeights()
    ts = type_score(candidate, query)
    as_ = aspect_score(candidate, query)
    ds = duration_score(candidate, query)
    gs = tag_score(candidate, query)
    rs = resolution_score(candidate, query)
    total = (w.type * ts + w.aspect * as_ + w.duration * ds
             + w.tags * gs + w.resolution * rs)
    breakdown = ScoreBreakdown(type=ts, aspect=as_, duration=ds, tags=gs,
                               resolution=rs, total=round(total, 6))
    return RankedCandidate(candidate=candidate, score=round(total, 6), breakdown=breakdown)


def rank_candidates(candidates, query: AssetQuery,
                    weights: RankWeights | None = None) -> list[RankedCandidate]:
    """Score and sort candidates best-first (deterministic tie-break on id).

    Returns a new list with ``rank`` set (0 = best). A cross-family candidate
    (type score 0) is kept but ranks last; the resolver decides whether to accept
    it via ``min_score``."""
    scored = [score_candidate(c, query, weights) for c in candidates]
    scored.sort(key=lambda rc: (-rc.score, rc.candidate.candidate_id))
    return [
        RankedCandidate(candidate=rc.candidate, score=rc.score,
                        breakdown=rc.breakdown, rank=i)
        for i, rc in enumerate(scored)
    ]
