"""Creator Studio integration (Phase C13) — browse, accept/reject, apply as patches.

Bridges the Media Intelligence Engine to the Creator Studio (Phase C12) **by
composition** — it drives a :class:`StudioSession`'s existing public commands and
never modifies the Studio, the Editing Engine, the Timeline IR, or the renderer.
A creator browses per-scene recommendations with their confidence, accepts one
(which applies an immutable ``ReplaceAssetPatch`` through the session) or rejects
it, and accepts the recommended music (a ``MusicPatch``). Accepted picks feed a
live project-wide consistency check. Deterministic: the same session + registry
always yields the same recommendations and the same applied patches.
"""
from __future__ import annotations

from dataclasses import dataclass

from creator_studio import StudioSession
from creator_studio.viewmodels import CommandResult

from media_intelligence.consistency import ConsistencyReport
from media_intelligence.engine import MediaIntelligenceEngine, MediaPlan
from media_intelligence.recommend import ProjectRecommendations, SceneRecommendation
from media_intelligence.registry import RegisteredAsset


@dataclass(frozen=True)
class RecommendationCard:
    """What the Studio shows for one scene: the pick, its confidence, and status."""

    scene_index: int
    kind: str
    layout: str
    asset_id: str | None
    confidence: float
    explanation: str
    n_alternatives: int
    status: str                          # "pending" | "accepted" | "rejected"


class MediaStudioController:
    """Media-recommendation panel over a live :class:`StudioSession`."""

    def __init__(self, session: StudioSession, engine: MediaIntelligenceEngine) -> None:
        self.session = session
        self.engine = engine
        self._accepted: dict[int, RegisteredAsset] = {}
        self._rejected: set[int] = set()
        self._plan_cache: tuple[int, MediaPlan] | None = None

    # ------------------------------------------------------------- decisions
    def plan(self) -> MediaPlan:
        """The full media plan for the current project (recomputed on edits)."""
        rev = self.session.revision
        if self._plan_cache is None or self._plan_cache[0] != rev:
            self._plan_cache = (rev, self.engine.plan(self.session.project))
        return self._plan_cache[1]

    def recommendations(self) -> ProjectRecommendations:
        return self.plan().recommendations

    def browse(self, scene_index: int) -> SceneRecommendation | None:
        return self.recommendations().for_scene(scene_index)

    def confidence(self, scene_index: int) -> float:
        rec = self.browse(scene_index)
        return rec.confidence if rec else 0.0

    def cards(self) -> tuple[RecommendationCard, ...]:
        """One :class:`RecommendationCard` per scene (for the browse panel)."""
        cards = []
        for rec in self.recommendations().scenes:
            i = rec.scene_index
            status = ("accepted" if i in self._accepted
                      else "rejected" if i in self._rejected else "pending")
            cards.append(RecommendationCard(
                scene_index=i, kind=rec.kind, layout=rec.layout,
                asset_id=rec.primary.asset.asset_id if rec.primary else None,
                confidence=rec.confidence, explanation=rec.explanation,
                n_alternatives=len(rec.alternatives), status=status))
        return tuple(cards)

    # --------------------------------------------------------- accept / reject
    def accept(self, scene_index: int) -> CommandResult:
        """Accept a scene's recommendation → apply an immutable ``ReplaceAssetPatch``.

        Routes through the session's existing ``replace_asset`` command (which
        builds the patch and calls the Editing Engine), so the project is never
        mutated directly. Records the chosen asset for the consistency check."""
        rec = self.browse(scene_index)
        if rec is None or not rec.has_recommendation:
            return CommandResult(
                ok=False, message=f"no recommendation for scene {scene_index}",
                revision=self.session.revision, problems=("no recommendation",))
        result = self.session.replace_asset(
            scene_index, asset_type=rec.kind, layout=rec.layout)
        if result.ok:
            self._accepted[scene_index] = rec.primary.asset
            self._rejected.discard(scene_index)
        return result

    def accept_alternative(self, scene_index: int, alt_index: int) -> CommandResult:
        """Accept one of a scene's alternative assets (same patch machinery)."""
        rec = self.browse(scene_index)
        if rec is None or alt_index >= len(rec.alternatives):
            return CommandResult(
                ok=False, message=f"no alternative {alt_index} for scene {scene_index}",
                revision=self.session.revision, problems=("no such alternative",))
        alt = rec.alternatives[alt_index]
        result = self.session.replace_asset(
            scene_index, asset_type=alt.asset.kind, layout=rec.layout)
        if result.ok:
            self._accepted[scene_index] = alt.asset
            self._rejected.discard(scene_index)
        return result

    def reject(self, scene_index: int) -> CommandResult:
        """Reject a scene's recommendation (no patch, no project change)."""
        self._rejected.add(scene_index)
        self._accepted.pop(scene_index, None)
        return CommandResult(ok=True, message=f"rejected scene {scene_index}",
                             revision=self.session.revision)

    def accept_music(self) -> CommandResult:
        """Accept the recommended soundtrack → apply an immutable ``MusicPatch``."""
        rec = self.plan().music
        return self.session.set_music(rec.soundtrack)

    def accept_all(self) -> tuple[CommandResult, ...]:
        """Accept every scene recommendation + the music, in scene order."""
        results = [self.accept(rec.scene_index)
                   for rec in self.recommendations().scenes if rec.has_recommendation]
        results.append(self.accept_music())
        return tuple(results)

    # ------------------------------------------------------------ consistency
    def accepted_assignments(self) -> dict[int, RegisteredAsset]:
        return dict(self._accepted)

    def consistency(self) -> ConsistencyReport:
        """Project-wide consistency of the accepted picks (falls back to all picks)."""
        assignments = self._accepted or {
            s.scene_index: s.primary.asset
            for s in self.recommendations().scenes if s.primary}
        return self.engine.analyze_consistency(assignments, project=self.session.project)

    @property
    def accepted(self) -> tuple[int, ...]:
        return tuple(sorted(self._accepted))

    @property
    def rejected(self) -> tuple[int, ...]:
        return tuple(sorted(self._rejected))
