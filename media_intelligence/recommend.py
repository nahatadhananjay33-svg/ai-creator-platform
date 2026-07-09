"""Asset Recommendation Engine (Phase C13) — deterministic B-roll suggestions.

For each storyboard scene it recommends the best-fitting B-roll asset (plus
alternatives) from the registry, with a **confidence score** and a plain-language
**explanation** of the decision. It is deterministic and rule-based: the query for
a scene is derived from its narration keywords, its declared/inferred asset kind,
and its estimated duration; ranking is the existing Phase C9 weighted ranker.

Crucially, a recommendation is *advisory* — it produces a **media decision**, not
a mutation. Turning a recommendation into an edit is an immutable
``ReplaceAssetPatch`` (see :meth:`SceneRecommendation.to_patch`), applied through
the Editing Engine exactly like any other edit; nothing here touches the project,
the Timeline IR, or the renderer.
"""
from __future__ import annotations

from dataclasses import dataclass

from reel_engine.interfaces.types import ASSET_KINDS

from editing_engine.patches.operations import ReplaceAssetPatch
from editing_engine.project import ReelProject
from script_engine.storyboard.types import ScriptScene

from asset_engine.catalog.index import tokenize_tags
from asset_engine.catalog.types import AssetQuery
from asset_engine.ranking.scorer import RankWeights

from media_intelligence.cache import AssetCache, cache_key
from media_intelligence.registry import AssetRegistry, RegisteredAsset
from media_intelligence.search import AssetSearchEngine, SearchHit

#: Deterministic default asset kind per scene type when the scene declares none.
_SCENE_TYPE_KIND = {
    "hook": "image", "talking_head": "image", "explanation": "image",
    "image_insert": "image", "video_insert": "video", "comparison": "chart",
    "bullet_list": "illustration", "chart": "chart", "quote": "illustration",
    "call_to_action": "image", "outro": "image",
}
#: Deterministic default on-screen layout per asset kind (what the patch sets).
_KIND_LAYOUT = {
    "video": "full_screen", "image": "full_screen", "chart": "full_screen",
    "screenshot": "full_screen", "map": "full_screen", "document": "picture_in_picture",
    "icon": "floating_card", "illustration": "picture_in_picture",
}


def infer_kind(scene: ScriptScene) -> str:
    """The asset kind to look for in a scene (declared kind wins; else by type)."""
    if scene.asset_type and scene.asset_type in ASSET_KINDS:
        return scene.asset_type
    return _SCENE_TYPE_KIND.get(scene.scene_type, "image")


def suggested_layout(scene: ScriptScene, kind: str) -> str:
    """The layout the recommendation would set (keeps a valid declared layout)."""
    from editing_engine.patches.base import VALID_ASSET_LAYOUTS
    if scene.layout and scene.layout in VALID_ASSET_LAYOUTS:
        return scene.layout
    return _KIND_LAYOUT.get(kind, "full_screen")


@dataclass(frozen=True)
class RecommendedAsset:
    """One recommended asset with its confidence + human-readable reasons."""

    asset: RegisteredAsset
    confidence: float                    # normalised relevance in [0, 1]
    rank: int
    reasons: tuple[str, ...]
    matched_tags: tuple[str, ...]

    @classmethod
    def from_hit(cls, hit: SearchHit, query: AssetQuery) -> "RecommendedAsset":
        matched = tuple(t for t in query.tags if t in hit.asset.tags)
        return cls(asset=hit.asset, confidence=hit.relevance, rank=hit.rank,
                   reasons=_explain(hit, query, matched), matched_tags=matched)


@dataclass(frozen=True)
class SceneRecommendation:
    """The B-roll decision for one scene: primary pick + alternatives + rationale."""

    scene_index: int
    kind: str
    layout: str
    query: AssetQuery
    primary: RecommendedAsset | None
    alternatives: tuple[RecommendedAsset, ...] = ()

    @property
    def has_recommendation(self) -> bool:
        return self.primary is not None

    @property
    def confidence(self) -> float:
        return self.primary.confidence if self.primary else 0.0

    @property
    def explanation(self) -> str:
        if not self.primary:
            return (f"scene {self.scene_index}: no {self.kind} asset in the registry "
                    f"matched (tags={list(self.query.tags)})")
        return (f"scene {self.scene_index}: {self.primary.asset.asset_id} "
                f"(confidence {self.primary.confidence:.0%}) — "
                + "; ".join(self.primary.reasons))

    def to_patch(self) -> ReplaceAssetPatch | None:
        """The immutable edit that applies this recommendation (or ``None``).

        A recommendation becomes a ``ReplaceAssetPatch`` setting the scene's asset
        kind + layout — routed through the Editing Engine like any other edit."""
        if not self.primary:
            return None
        return ReplaceAssetPatch(index=self.scene_index, asset_type=self.kind,
                                 layout=self.layout)


@dataclass(frozen=True)
class ProjectRecommendations:
    """All per-scene B-roll recommendations for a project."""

    scenes: tuple[SceneRecommendation, ...]

    @property
    def n_scenes(self) -> int:
        return len(self.scenes)

    @property
    def recommended(self) -> tuple[SceneRecommendation, ...]:
        return tuple(s for s in self.scenes if s.has_recommendation)

    @property
    def mean_confidence(self) -> float:
        recs = self.recommended
        return round(sum(s.confidence for s in recs) / len(recs), 6) if recs else 0.0

    def patches(self) -> tuple[ReplaceAssetPatch, ...]:
        return tuple(p for s in self.scenes if (p := s.to_patch()) is not None)

    def for_scene(self, index: int) -> SceneRecommendation | None:
        return next((s for s in self.scenes if s.scene_index == index), None)


def _explain(hit: SearchHit, query: AssetQuery, matched: tuple[str, ...]) -> tuple[str, ...]:
    """Deterministic reasons a candidate was recommended, from its breakdown."""
    b = hit.breakdown
    reasons: list[str] = []
    if b.type >= 1.0:
        reasons.append(f"kind matches ({hit.asset.kind})")
    elif b.type > 0.0:
        reasons.append(f"same family as {query.kind}")
    if query.tags:
        reasons.append(f"{len(matched)}/{len(query.tags)} tags matched "
                       + (f"[{', '.join(matched)}]" if matched else "[none]"))
    if query.target_aspect > 0:
        reasons.append(f"aspect fit {b.aspect:.0%}")
    if query.family == "video" and query.target_duration_s > 0:
        reasons.append(f"duration fit {b.duration:.0%}")
    reasons.append(f"license {hit.asset.license}")
    return tuple(reasons)


class AssetRecommendationEngine:
    """Recommends B-roll (primary + alternatives) for each scene, deterministically."""

    def __init__(self, registry: AssetRegistry, *, search_engine: AssetSearchEngine | None = None,
                 weights: RankWeights | None = None, cache: AssetCache | None = None) -> None:
        self.registry = registry
        self.cache = cache
        self.search = search_engine or AssetSearchEngine(
            registry, weights=weights, cache=cache)

    # ------------------------------------------------------------ per scene
    def query_for(self, scene: ScriptScene) -> tuple[str, str, AssetQuery]:
        """Return ``(kind, layout, query)`` for a scene (all deterministic)."""
        kind = infer_kind(scene)
        layout = suggested_layout(scene, kind)
        tags = list(scene.keywords)
        for t in tokenize_tags(scene.narration):
            if t not in tags:
                tags.append(t)
        duration = scene.duration_estimate_s if kind == "video" else 0.0
        query = self.search.build_query(
            kind=kind, tags=tuple(tags), target_duration_s=round(duration, 3),
            slot_id=f"scene-{0}")
        return kind, layout, query

    def recommend_for_scene(self, project: ReelProject, index: int, *,
                            n_alternatives: int = 2) -> SceneRecommendation:
        scene = project.scenes[index]
        kind, layout, query = self.query_for(scene)
        query = _with_slot(query, f"scene-{index:03d}")
        hits = self.search.search_query(query, limit=1 + max(0, n_alternatives))
        primary = RecommendedAsset.from_hit(hits[0], query) if hits else None
        alts = tuple(RecommendedAsset.from_hit(h, query) for h in hits[1:])
        return SceneRecommendation(
            scene_index=index, kind=kind, layout=layout, query=query,
            primary=primary, alternatives=alts)

    def recommend_for_project(self, project: ReelProject, *,
                              n_alternatives: int = 2) -> ProjectRecommendations:
        """B-roll recommendations for every scene (cached by project identity)."""
        def _compute() -> ProjectRecommendations:
            return ProjectRecommendations(tuple(
                self.recommend_for_scene(project, i, n_alternatives=n_alternatives)
                for i in range(project.n_scenes)))
        if self.cache is not None:
            key = cache_key("recommend", _project_key(project), n_alternatives,
                            self.registry.size)
            return self.cache.get_or_compute(key, _compute)
        return _compute()

    def alternatives(self, project: ReelProject, index: int, *, n: int = 5) -> tuple[RecommendedAsset, ...]:
        """The top ``n`` alternative assets for a scene (primary included first)."""
        rec = self.recommend_for_scene(project, index, n_alternatives=n)
        primary = (rec.primary,) if rec.primary else ()
        return (primary + rec.alternatives)[:n]


def _with_slot(query: AssetQuery, slot_id: str) -> AssetQuery:
    from dataclasses import replace
    return replace(query, slot_id=slot_id)


def _project_key(project: ReelProject) -> str:
    parts = [project.storyboard.title, str(project.revision)]
    for s in project.scenes:
        parts.append(f"{s.scene_type}:{s.asset_type}:{s.narration}")
    return "|".join(parts)
