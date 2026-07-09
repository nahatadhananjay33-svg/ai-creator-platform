"""Media Intelligence & Asset Management Engine (Phase C13).

A deterministic media-intelligence layer that sits **between** the AI Storyboard
Engine and the Editing Engine. It selects, validates, ranks, recommends, caches,
and replaces the media assets a :class:`~editing_engine.ReelProject` uses — and it
produces **media decisions only**:

- it never mutates a project — every actionable decision becomes an immutable
  ``Patch`` (``ReplaceAssetPatch`` / ``MusicPatch``) applied through the Editing
  Engine;
- the **Timeline IR, renderer, and Editing Engine are all unchanged**;
- everything is deterministic and hermetic (mock providers for every external
  AI/media service);
- it reuses the existing Phase C9 retrieval/ranking pipeline rather than
  duplicating it.

    AI Storyboard ─► Media Intelligence (registry / search / recommend / consistency)
                  ─► immutable patches ─► Editing Engine ─► Timeline ─► renderer ─► MP4

Public API:
- :class:`MediaIntelligenceEngine` — the facade (search, recommend, plan)
- :class:`AssetRegistry` / :class:`RegisteredAsset` — the central asset catalog
- :class:`AssetSearchEngine` — deterministic semantic search + ranking
- :class:`AssetRecommendationEngine` — per-scene B-roll recommendations
- :class:`ConsistencyEngine` — project-wide visual coherence
- :class:`MusicRecommender` / :class:`VoiceRecommender` — soundtrack + narrator
- :class:`AssetCache` — deterministic decision cache
- :class:`MediaProvider` + mocks/stubs — the provider seam
- :class:`MediaStudioController` — the Creator Studio integration
"""
from __future__ import annotations

from media_intelligence.cache import AssetCache, CacheStats, cache_key
from media_intelligence.consistency import (
    ConsistencyEngine,
    ConsistencyFinding,
    ConsistencyReport,
)
from media_intelligence.engine import MediaIntelligenceEngine, MediaPlan
from media_intelligence.music import MusicRecommendation, MusicRecommender
from media_intelligence.providers import (
    FUTURE_SERVICES,
    REAL_PROVIDERS,
    MediaProvider,
    MockMediaProvider,
    all_mock_providers,
    mock_provider_for,
)
from media_intelligence.recommend import (
    AssetRecommendationEngine,
    ProjectRecommendations,
    RecommendedAsset,
    SceneRecommendation,
    infer_kind,
    suggested_layout,
)
from media_intelligence.registry import (
    LICENSES,
    AssetRegistry,
    RegisteredAsset,
    RegistryProvider,
    RegistryStats,
    make_asset_id,
)
from media_intelligence.search import AssetSearchEngine, SearchHit
from media_intelligence.studio import MediaStudioController, RecommendationCard
from media_intelligence.voice import (
    VOICE_CATALOG,
    VoiceMeta,
    VoiceRecommendation,
    VoiceRecommender,
)

__version__ = "1.0.0"

__all__ = [
    "MediaIntelligenceEngine",
    "MediaPlan",
    "AssetRegistry",
    "RegisteredAsset",
    "RegistryProvider",
    "RegistryStats",
    "make_asset_id",
    "LICENSES",
    "AssetSearchEngine",
    "SearchHit",
    "AssetRecommendationEngine",
    "ProjectRecommendations",
    "SceneRecommendation",
    "RecommendedAsset",
    "infer_kind",
    "suggested_layout",
    "ConsistencyEngine",
    "ConsistencyReport",
    "ConsistencyFinding",
    "MusicRecommender",
    "MusicRecommendation",
    "VoiceRecommender",
    "VoiceRecommendation",
    "VoiceMeta",
    "VOICE_CATALOG",
    "AssetCache",
    "CacheStats",
    "cache_key",
    "MediaProvider",
    "MockMediaProvider",
    "mock_provider_for",
    "all_mock_providers",
    "FUTURE_SERVICES",
    "REAL_PROVIDERS",
    "MediaStudioController",
    "RecommendationCard",
]
