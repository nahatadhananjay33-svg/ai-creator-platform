"""Deterministic asset resolver (Phase C9).

The pipeline hub: ``AssetSlot → query → candidates → ranking → selection``. For a
slot it builds the query, gathers candidates from the :class:`ProviderManager`,
ranks them, and selects the best **same-family** candidate whose score clears
``min_score`` (a still is never chosen for a video slot, or vice versa). The
result is a :class:`Resolution` carrying the selection and the full ranking, so
callers can see *why* an asset was chosen. Fully deterministic — no AI anywhere.
"""
from __future__ import annotations

from dataclasses import dataclass

from asset_engine.catalog.types import AssetCandidate, AssetQuery
from asset_engine.ranking.scorer import RankedCandidate, RankWeights, rank_candidates
from asset_engine.resolver.manager import ProviderManager
from asset_engine.resolver.query import build_query


class AssetResolutionError(Exception):
    """A required :class:`AssetSlot` could not be satisfied by any provider."""


@dataclass(frozen=True)
class Resolution:
    """The outcome of resolving one query: the pick + the full ranking."""

    slot_id: str
    query: AssetQuery
    selected: RankedCandidate | None
    ranked: tuple

    @property
    def satisfied(self) -> bool:
        return self.selected is not None

    @property
    def candidate(self) -> AssetCandidate | None:
        return self.selected.candidate if self.selected else None

    @property
    def score(self) -> float:
        return self.selected.score if self.selected else 0.0


class AssetResolver:
    """Resolves slots/queries to assets via a provider manager + ranking."""

    def __init__(self, manager: ProviderManager, *, weights: RankWeights | None = None,
                 min_score: float = 0.0, per_provider_limit: int = 16) -> None:
        self.manager = manager
        self.weights = weights or RankWeights()
        self.min_score = min_score
        self.per_provider_limit = per_provider_limit

    def resolve_query(self, query: AssetQuery) -> Resolution:
        """Gather → rank → select the best same-family candidate for ``query``."""
        candidates = self.manager.candidates(
            query, per_provider_limit=self.per_provider_limit)
        ranked = rank_candidates(candidates, query, self.weights)
        selected = next(
            (rc for rc in ranked
             if rc.breakdown.type > 0.0 and rc.score >= self.min_score), None)
        return Resolution(slot_id=query.slot_id, query=query,
                          selected=selected, ranked=tuple(ranked))

    def resolve_slot(self, slot, *, frame_width: int = 1080,
                     frame_height: int = 1920) -> Resolution:
        """Resolve one ``AssetSlot`` (read structurally)."""
        return self.resolve_query(
            build_query(slot, frame_width=frame_width, frame_height=frame_height))

    def resolve_slots(self, slots, *, frame_width: int = 1080,
                      frame_height: int = 1920) -> list[Resolution]:
        """Resolve a sequence of slots, in order."""
        return [self.resolve_slot(s, frame_width=frame_width, frame_height=frame_height)
                for s in slots]
