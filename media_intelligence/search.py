"""Asset Search Engine (Phase C13) — deterministic semantic search + ranking.

Searches the :class:`AssetRegistry` for the assets that best satisfy a need
expressed as free text (a scene's narration/keywords) or a structured
:class:`AssetQuery`. "Semantic" here is a **deterministic mock**: free text is
tokenised into tags (the existing catalog tokeniser) and matched with the existing
Phase C9 weighted ranker — NO embeddings, NO model, NO randomness. The same query
over the same registry always returns the same ranking, with ties broken on the
stable candidate ID.

Results carry a normalised **relevance** in ``[0, 1]`` (the ranking score over the
maximum achievable score) plus the full score breakdown, so callers can show *why*
an asset ranked where it did.
"""
from __future__ import annotations

from dataclasses import dataclass

from asset_engine.catalog.index import tokenize_tags
from asset_engine.catalog.types import AssetQuery
from asset_engine.ranking.scorer import RankWeights, ScoreBreakdown, rank_candidates

from media_intelligence.cache import AssetCache, cache_key
from media_intelligence.registry import AssetRegistry, RegisteredAsset


@dataclass(frozen=True)
class SearchHit:
    """One ranked search result: the asset, its position, and a normalised score."""

    asset: RegisteredAsset
    score: float                         # raw weighted score
    relevance: float                     # score normalised to [0, 1]
    rank: int                            # 0 = best
    breakdown: ScoreBreakdown

    @property
    def matched(self) -> bool:
        """Whether the hit is a real (same-family, non-zero type) match."""
        return self.breakdown.type > 0.0


class AssetSearchEngine:
    """Deterministic semantic search + ranking over an :class:`AssetRegistry`."""

    def __init__(self, registry: AssetRegistry, *, weights: RankWeights | None = None,
                 cache: AssetCache | None = None) -> None:
        self.registry = registry
        self.weights = weights or RankWeights()
        self.cache = cache

    # --------------------------------------------------------------- queries
    def build_query(self, text: str = "", *, kind: str = "", tags=(),
                    target_aspect: float = 0.0, target_duration_s: float = 0.0,
                    min_width: int = 0, min_height: int = 0, slot_id: str = "") -> AssetQuery:
        """Build a deterministic :class:`AssetQuery` from free text + hints.

        Tags come from the explicit ``tags`` plus the tokenised ``text`` (dedup,
        stable order), so a plain-language search still ranks by tag overlap."""
        toks = list(tags)
        for t in tokenize_tags(text):
            if t not in toks:
                toks.append(t)
        return AssetQuery(
            kind=kind or "image", tags=tuple(toks), target_aspect=target_aspect,
            target_duration_s=target_duration_s, min_width=min_width,
            min_height=min_height, slot_id=slot_id)

    # ---------------------------------------------------------------- search
    def search_query(self, query: AssetQuery, *, limit: int = 8,
                     include_unmatched: bool = False) -> list[SearchHit]:
        """Rank the registry against ``query`` and return the top ``limit`` hits.

        Cross-family candidates (a still for a video slot) score 0 on type and are
        dropped unless ``include_unmatched`` is set. Cached by (query, limit,
        include_unmatched) when a cache is attached."""
        if self.cache is not None:
            key = cache_key("search", _query_key(query), limit, include_unmatched,
                            self.registry.size)
            return self.cache.get_or_compute(
                key, lambda: self._search(query, limit, include_unmatched))
        return self._search(query, limit, include_unmatched)

    def search(self, text: str = "", *, kind: str = "", tags=(), limit: int = 8,
               target_duration_s: float = 0.0, include_unmatched: bool = False) -> list[SearchHit]:
        """Convenience: free-text (+ optional kind/tags) search."""
        query = self.build_query(text, kind=kind, tags=tags,
                                 target_duration_s=target_duration_s)
        return self.search_query(query, limit=limit, include_unmatched=include_unmatched)

    def best(self, text: str = "", *, kind: str = "", tags=(),
             target_duration_s: float = 0.0) -> SearchHit | None:
        """The single best matching asset, or ``None`` if nothing matches."""
        hits = self.search(text, kind=kind, tags=tags, limit=1,
                           target_duration_s=target_duration_s)
        return hits[0] if hits else None

    # -------------------------------------------------------------- internals
    def _search(self, query: AssetQuery, limit: int, include_unmatched: bool) -> list[SearchHit]:
        provider = self.registry.as_provider()
        candidates = provider.search(query, limit=0)         # all family-compatible
        ranked = rank_candidates(candidates, query, self.weights)
        max_score = self.weights.total or 1.0
        hits: list[SearchHit] = []
        for rc in ranked:
            if rc.breakdown.type <= 0.0 and not include_unmatched:
                continue
            asset = self._asset_for(rc.candidate)
            if asset is None:
                continue
            hits.append(SearchHit(
                asset=asset, score=rc.score,
                relevance=round(min(1.0, rc.score / max_score), 6),
                rank=len(hits), breakdown=rc.breakdown))
            if limit and len(hits) >= limit:
                break
        return hits

    def _asset_for(self, candidate) -> RegisteredAsset | None:
        """Recover the registry asset behind a candidate (via its stamped ID)."""
        aid = candidate.meta.get("asset_id")
        if aid:
            return self.registry.get(aid)
        # candidate_id is "<provider>:<asset_id>"
        _, _, tail = candidate.candidate_id.partition(":")
        return self.registry.get(tail)


def _query_key(query: AssetQuery) -> str:
    """A stable string identity for a query (for cache keys)."""
    return "/".join((query.kind, ",".join(query.tags),
                     f"{query.target_aspect}", f"{query.target_duration_s}",
                     f"{query.min_width}x{query.min_height}"))
