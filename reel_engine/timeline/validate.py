"""Timeline validation (Phase C2).

A Timeline must be *renderable* before any backend touches it: right schema,
even encoder-friendly dimensions, positive fps/durations, and at least one
solid background per scene. Validation returns a list of human-readable
problems (empty == valid); ``validate_or_raise`` turns a non-empty list into a
single :class:`TimelineError`. No renderer, no I/O — pure inspection.
"""
from __future__ import annotations

from foundation.exceptions import ConfigError
from reel_engine.interfaces.types import TIMELINE_SCHEMA_VERSION, Clip, Timeline


class TimelineError(ConfigError):
    """A Timeline is structurally invalid / not renderable."""


def _valid_rgb(color) -> bool:
    return (isinstance(color, (tuple, list)) and len(color) == 3
            and all(isinstance(c, int) and 0 <= c <= 255 for c in color))


def _validate_clip(clip: Clip, scene_duration: float, where: str) -> list[str]:
    problems: list[str] = []
    if clip.end_s <= clip.start_s:
        problems.append(f"{where}: clip {clip.clip_id!r} has end_s <= start_s")
    if clip.start_s < -1e-6 or clip.end_s > scene_duration + 1e-6:
        problems.append(
            f"{where}: clip {clip.clip_id!r} time [{clip.start_s}, {clip.end_s}] "
            f"is outside the scene [0, {scene_duration}]"
        )
    if clip.kind == "solid_color" and not _valid_rgb(clip.color):
        problems.append(f"{where}: solid_color clip {clip.clip_id!r} has an invalid RGB colour")
    if clip.kind == "text" and not (clip.text and clip.text.strip()):
        problems.append(f"{where}: text clip {clip.clip_id!r} has empty text")
    return problems


def validate_timeline(tl: Timeline) -> list[str]:
    """Return a list of problems; empty means the Timeline is renderable."""
    problems: list[str] = []

    if tl.schema_version > TIMELINE_SCHEMA_VERSION:
        problems.append(
            f"schema_version {tl.schema_version} newer than supported "
            f"{TIMELINE_SCHEMA_VERSION}"
        )

    m = tl.meta
    if m.width <= 0 or m.height <= 0:
        problems.append(f"meta: non-positive resolution {m.width}x{m.height}")
    if m.width % 2 or m.height % 2:
        # yuv420p (h264/nvenc default) requires even dimensions.
        problems.append(f"meta: resolution {m.width}x{m.height} must have even dimensions")
    if m.fps <= 0:
        problems.append(f"meta: fps must be positive, got {m.fps}")
    if not _valid_rgb(m.background_default):
        problems.append("meta: background_default is not a valid RGB triple")

    if not tl.scenes:
        problems.append("timeline has no scenes")

    seen_ids: set[str] = set()
    for i, scene in enumerate(tl.scenes):
        where = f"scene[{i}] {scene.scene_id!r}"
        if scene.scene_id in seen_ids:
            problems.append(f"{where}: duplicate scene_id")
        seen_ids.add(scene.scene_id)
        if scene.duration_s <= 0:
            problems.append(f"{where}: duration_s must be positive, got {scene.duration_s}")
        bg = scene.track("background")
        if bg is None or not bg.clips:
            problems.append(f"{where}: no background track/clip (nothing to render)")
        for track in scene.tracks:
            for clip in track.clips:
                problems.extend(_validate_clip(clip, scene.duration_s, where))

    return problems


def validate_or_raise(tl: Timeline) -> Timeline:
    """Return ``tl`` if valid, else raise :class:`TimelineError` listing every
    problem at once (so the caller fixes them in one pass)."""
    problems = validate_timeline(tl)
    if problems:
        raise TimelineError("Timeline is not renderable", problems=problems)
    return tl
