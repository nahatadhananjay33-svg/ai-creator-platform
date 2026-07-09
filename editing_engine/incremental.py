"""Incremental rendering plan (Phase C11).

After an edit, most scenes are usually unchanged — so re-rendering the whole reel
is wasteful. This module computes, from two timelines, WHICH scenes actually
changed, by reusing the existing Timeline per-scene content hashes
(:func:`reel_engine.timeline.hashing.scene_content_hash`). It does **not** modify
the renderer or the Timeline IR — it produces a plan a future renderer (or Creator
Studio) can consume to re-render only the changed scenes and reuse cached renders
for the rest.

    old timeline  ─┐
                   ├─► plan_incremental ─► IncrementalPlan (changed / reused / cacheable)
    new timeline  ─┘
"""
from __future__ import annotations

from dataclasses import dataclass

from foundation.shared_utils.hashing import sha256_text
from reel_engine.interfaces.types import Timeline
from reel_engine.timeline.hashing import canonical_json, scene_content_hash
from reel_engine.timeline.serde import timeline_to_dict


@dataclass(frozen=True)
class IncrementalPlan:
    """Which scenes must be re-rendered vs reused between two timelines.

    Indices refer to the NEW timeline. ``changed`` scenes differ from the old
    scene at the same position (must re-render); ``reused`` are byte-identical at
    the same position (skip). ``cacheable`` scenes have a hash present ANYWHERE in
    the old timeline — a reorder moves a scene but its render can still be reused
    from cache. ``overlays_changed`` flags a caption/branding/music/asset change
    that requires re-compositing overlays even when no scene changed."""

    total: int
    changed: tuple[int, ...]
    reused: tuple[int, ...]
    cacheable: tuple[int, ...]
    overlays_changed: bool

    @property
    def n_changed(self) -> int:
        return len(self.changed)

    @property
    def n_reused(self) -> int:
        return len(self.reused)

    @property
    def reuse_fraction(self) -> float:
        """Fraction of NEW scenes whose render can be reused (0..1)."""
        return round(self.n_reused / self.total, 4) if self.total else 1.0

    @property
    def needs_render(self) -> bool:
        """True if anything at all must be re-rendered/re-composited."""
        return bool(self.changed) or self.overlays_changed


def _overlay_signature(timeline: Timeline) -> str:
    """A stable hash of everything EXCEPT the scenes (captions/branding/music/
    assets/meta) — so an overlay-only edit is detectable independently."""
    d = timeline_to_dict(timeline)
    d.pop("scenes", None)
    return sha256_text(canonical_json(d))


def plan_incremental(old: Timeline, new: Timeline) -> IncrementalPlan:
    """Compute the :class:`IncrementalPlan` from ``old`` to ``new`` (deterministic)."""
    old_hashes = [scene_content_hash(s) for s in old.scenes]
    new_hashes = [scene_content_hash(s) for s in new.scenes]
    old_set = set(old_hashes)

    changed: list[int] = []
    reused: list[int] = []
    cacheable: list[int] = []
    for i, h in enumerate(new_hashes):
        if i < len(old_hashes) and old_hashes[i] == h:
            reused.append(i)
        else:
            changed.append(i)
        if h in old_set:
            cacheable.append(i)

    overlays_changed = _overlay_signature(old) != _overlay_signature(new)
    return IncrementalPlan(
        total=len(new_hashes), changed=tuple(changed), reused=tuple(reused),
        cacheable=tuple(cacheable), overlays_changed=overlays_changed)
