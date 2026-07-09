"""Media Intelligence Engine (Phase C13) — the facade.

The single entry point that ties the registry, search, recommendation,
consistency, music, voice, cache, and provider layers together. It sits **between**
the AI Storyboard Engine and the Editing Engine: it takes a
:class:`~editing_engine.ReelProject` and produces **media decisions** — B-roll
recommendations, ranked search results, a soundtrack, a narrator voice, and a
project-wide consistency report — never mutating the project. Every actionable
decision exposes an immutable ``Patch`` (``ReplaceAssetPatch`` / ``MusicPatch``) so
the Editing Engine remains the only thing that changes a project. Deterministic
throughout; the Timeline IR and renderer are untouched.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from editing_engine.patches.operations import MusicPatch, ReplaceAssetPatch
from editing_engine.project import ReelProject

from asset_engine.catalog.index import AssetCatalog
from asset_engine.ranking.scorer import RankWeights

from media_intelligence.cache import AssetCache
from media_intelligence.consistency import ConsistencyEngine, ConsistencyReport
from media_intelligence.music import MusicRecommendation, MusicRecommender
from media_intelligence.recommend import (
    AssetRecommendationEngine,
    ProjectRecommendations,
    SceneRecommendation,
)
from media_intelligence.registry import AssetRegistry, RegisteredAsset
from media_intelligence.search import AssetSearchEngine, SearchHit
from media_intelligence.voice import VoiceRecommendation, VoiceRecommender


@dataclass(frozen=True)
class MediaPlan:
    """A full, deterministic media plan for a project (all decisions in one value).

    Everything actionable is expressible as immutable patches via
    :meth:`patches`, so applying a plan is just routing those through the Editing
    Engine."""

    recommendations: ProjectRecommendations
    music: MusicRecommendation
    voice: VoiceRecommendation
    consistency: ConsistencyReport

    def patches(self) -> tuple:
        """Every immutable patch this plan implies (asset replacements + music)."""
        return (*self.recommendations.patches(), self.music.to_patch())


class MediaIntelligenceEngine:
    """Produces deterministic media decisions for a project (the C13 facade)."""

    def __init__(self, registry: AssetRegistry, *, weights: RankWeights | None = None,
                 cache: AssetCache | None = None) -> None:
        self.registry = registry
        self.cache = cache or AssetCache()
        self.weights = weights or RankWeights()
        self.search_engine = AssetSearchEngine(registry, weights=self.weights, cache=self.cache)
        self.recommender = AssetRecommendationEngine(
            registry, search_engine=self.search_engine, cache=self.cache)
        self.consistency_engine = ConsistencyEngine()
        self.music_recommender = MusicRecommender()
        self.voice_recommender = VoiceRecommender()

    # ------------------------------------------------------------- builders
    @classmethod
    def from_assets(cls, assets, **kwargs) -> "MediaIntelligenceEngine":
        return cls(AssetRegistry(assets), **kwargs)

    @classmethod
    def from_catalog(cls, catalog: AssetCatalog, *, source: str = "library",
                     license: str = "unknown", **kwargs) -> "MediaIntelligenceEngine":
        return cls(AssetRegistry.from_catalog(catalog, source=source, license=license), **kwargs)

    @classmethod
    def from_directory(cls, root: Path | str, *, source: str = "library",
                       license: str = "unknown", probe_videos: bool = False,
                       **kwargs) -> "MediaIntelligenceEngine":
        registry = AssetRegistry.from_directory(
            root, source=source, license=license, probe_videos=probe_videos)
        return cls(registry, **kwargs)

    # --------------------------------------------------------- media decisions
    def search(self, text: str = "", *, kind: str = "", tags=(), limit: int = 8,
               target_duration_s: float = 0.0) -> list[SearchHit]:
        return self.search_engine.search(
            text, kind=kind, tags=tags, limit=limit, target_duration_s=target_duration_s)

    def best(self, text: str = "", *, kind: str = "", tags=(),
             target_duration_s: float = 0.0) -> SearchHit | None:
        """The single best-matching asset for a free-text query (or ``None``)."""
        return self.search_engine.best(
            text, kind=kind, tags=tags, target_duration_s=target_duration_s)

    def recommend_broll(self, project: ReelProject, *, n_alternatives: int = 2
                        ) -> ProjectRecommendations:
        return self.recommender.recommend_for_project(project, n_alternatives=n_alternatives)

    def recommend_scene(self, project: ReelProject, index: int, *, n_alternatives: int = 2
                        ) -> SceneRecommendation:
        return self.recommender.recommend_for_scene(project, index, n_alternatives=n_alternatives)

    def recommend_music(self, project: ReelProject) -> MusicRecommendation:
        return self.music_recommender.recommend_music(project)

    def recommend_voice(self, project: ReelProject, *, language: str = "en"
                        ) -> VoiceRecommendation:
        return self.voice_recommender.recommend_voice(project, language=language)

    def analyze_consistency(self, assignments: dict[int, RegisteredAsset], *,
                            project: ReelProject | None = None) -> ConsistencyReport:
        return self.consistency_engine.analyze(assignments, project=project)

    def plan(self, project: ReelProject, *, language: str = "en",
             n_alternatives: int = 2) -> MediaPlan:
        """The full media plan (recommendations + music + voice + consistency)."""
        recs = self.recommend_broll(project, n_alternatives=n_alternatives)
        return MediaPlan(
            recommendations=recs,
            music=self.recommend_music(project),
            voice=self.recommend_voice(project, language=language),
            consistency=self.consistency_engine.analyze_recommendations(recs, project=project))

    # ------------------------------------------------------------------ stats
    def cache_stats(self):
        return self.cache.stats()

    def registry_stats(self):
        return self.registry.stats()
