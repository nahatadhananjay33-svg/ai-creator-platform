"""Storyboard -> Timeline IR builder (Phase C7).

Lowers a deterministic :class:`Storyboard` into the existing, frozen
``reel_engine`` Timeline IR — the SAME IR the Reels/Caption/Branding/Asset
engines already produce and the renderer already consumes. The Storyboard does
NOT modify or replace the renderer; it feeds it.

What it builds:
  - one :class:`Scene` per scene plan — a solid card (the scene-type background
    hint) titled with the scene-type label, holding the narration as its silent
    bed's implicit copy. This is the deterministic stand-in for real avatar/B-roll
    footage (exactly how the C6 demo stands in for footage), and it is fully
    renderable and valid on its own.
  - a native :class:`CaptionTrack` built straight from the plan: one caption
    segment per scene, spanning that scene's absolute window, carrying its
    narration. Because the windows come from the same :class:`TimingPlan`, the
    captions are guaranteed aligned, monotonic, non-overlapping, and inside the
    reel — the invariants the Timeline validator enforces.

Asset slots are intentionally NOT lowered here: the planner only *requests*
assets; the Visual Asset Engine satisfies them in a later phase (this keeps the
"no retrieval" rule). :func:`asset_slot_windows` exposes the slots for a caller
(e.g. the demo) that wants to satisfy them with real files and stack an
``AssetTrack`` itself.
"""
from __future__ import annotations

import dataclasses

from reel_engine.interfaces.types import (
    CaptionSegment,
    CaptionStyle,
    CaptionTrack,
    Scene,
    Timeline,
)
from reel_engine.timeline.model import new_timeline

from scene_engine.storyboard.types import AssetSlot, Storyboard


def build_timeline(
    storyboard: Storyboard,
    *,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
    title: str | None = None,
    with_captions: bool = True,
    caption_kind: str = "sentence",
    caption_style: CaptionStyle | None = None,
    show_labels: bool = True,
    validate: bool = True,
) -> Timeline:
    """Build a validated :class:`Timeline` from a :class:`Storyboard`.

    Each scene plan becomes a solid-card :class:`Scene`; captions (on by default)
    come from the plan's narration and timing. Set ``show_labels=False`` for
    blank cards (captions still carry the narration).
    """
    scenes = []
    for sp in storyboard.scenes:
        label = sp.scene_type.label if show_labels else None
        role = ("title" if sp.index == 0
                else "cta" if sp.index == storyboard.n_scenes - 1 else "subtitle")
        scenes.append(Scene.simple(
            index=sp.index, color=tuple(sp.visual.background), text=label,
            duration_s=sp.duration_s, scene_id=sp.scene_id, text_role=role))

    tl = new_timeline(
        scenes, title=title or storyboard.title,
        width=width, height=height, fps=fps, validate=False)

    if with_captions:
        track = build_caption_track(storyboard, kind=caption_kind, style=caption_style)
        tl = dataclasses.replace(tl, caption_tracks=(track,))

    if validate:
        from reel_engine.timeline.validate import validate_or_raise
        return validate_or_raise(tl)
    return tl


def build_caption_track(
    storyboard: Storyboard,
    *,
    kind: str = "sentence",
    style: CaptionStyle | None = None,
    track_id: str = "captions",
) -> CaptionTrack:
    """One caption segment per scene, aligned to the plan's scene windows.

    Deterministic and self-contained (no Caption Engine dependency at build time):
    the segment window is exactly the scene's absolute ``[start_s, end_s]``, so
    the track is monotonic, non-overlapping, and bounded by the reel duration.
    Only scenes whose caption slot is present and whose narration is non-empty
    produce a segment.
    """
    segments: list[CaptionSegment] = []
    idx = 0
    for sp in storyboard.scenes:
        text = sp.narration.text.strip()
        if not (sp.visual.caption.present and text):
            continue
        segments.append(CaptionSegment(
            segment_id=f"seg-{idx:03d}", index=idx, text=text,
            start_s=sp.timing.start_s, end_s=sp.timing.end_s))
        idx += 1
    return CaptionTrack(track_id=track_id, kind=kind, segments=tuple(segments),
                        style=style or CaptionStyle())


def asset_slot_windows(storyboard: Storyboard) -> tuple[AssetSlot, ...]:
    """Every asset slot the storyboard requests, in play order.

    A convenience for a downstream Visual Asset Engine (or the demo) that wants to
    satisfy the plan's slots with concrete files — the Scene Engine itself never
    retrieves them."""
    return storyboard.all_asset_slots
