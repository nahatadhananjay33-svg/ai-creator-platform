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
    # C3 media clips (video footage / real audio) reference a source file whose
    # uri the renderer decodes — an empty source makes the scene unrenderable.
    if clip.kind in ("video", "audio_file") and not (clip.source and clip.source.uri):
        problems.append(f"{where}: {clip.kind} clip {clip.clip_id!r} has no source file")
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
        # A scene is renderable if it has *something* to draw the frame from:
        # a solid-colour background (C2) or a foreground video file (C3).
        bg = scene.track("background")
        vid = scene.track("video")
        has_background = bg is not None and bg.clips
        has_video = vid is not None and vid.clips
        if not has_background and not has_video:
            problems.append(f"{where}: no background or video track/clip (nothing to render)")
        for track in scene.tracks:
            for clip in track.clips:
                problems.extend(_validate_clip(clip, scene.duration_s, where))

    # Captions are timed in ABSOLUTE reel time; the reel (audio) duration is the
    # sum of scene durations. Empty caption_tracks (v1 timelines) skip this.
    reel_duration = tl.duration_s
    caption_ids: set[str] = set()
    for i, track in enumerate(tl.caption_tracks):
        problems.extend(_validate_caption_track(track, i, reel_duration, caption_ids))

    return problems


_CAPTION_KINDS = ("sentence", "word", "karaoke", "static")
_ALIGNMENTS = ("left", "center", "right")
_POSITIONS = ("top", "center", "bottom")
_ANIMATIONS = ("none", "fade", "pop")
_EPS = 1e-6


def _validate_caption_style(style, where: str) -> list[str]:
    problems: list[str] = []
    if style.alignment not in _ALIGNMENTS:
        problems.append(f"{where}: style.alignment {style.alignment!r} not in {_ALIGNMENTS}")
    if style.position not in _POSITIONS:
        problems.append(f"{where}: style.position {style.position!r} not in {_POSITIONS}")
    if style.font_size <= 0:
        problems.append(f"{where}: style.font_size must be positive, got {style.font_size}")
    for name in ("primary_color", "highlight_color", "outline_color",
                 "shadow_color", "box_color"):
        if not _valid_rgb(getattr(style, name)):
            problems.append(f"{where}: style.{name} is not a valid RGB triple")
    if not (0.0 <= style.safe_margin_v < 0.5):
        problems.append(f"{where}: style.safe_margin_v must be in [0, 0.5), got {style.safe_margin_v}")
    if not (0.0 <= style.safe_margin_h < 0.5):
        problems.append(f"{where}: style.safe_margin_h must be in [0, 0.5), got {style.safe_margin_h}")
    if not (0.0 <= style.box_opacity <= 1.0):
        problems.append(f"{where}: style.box_opacity must be in [0, 1], got {style.box_opacity}")
    return problems


def _validate_words(seg, where: str) -> list[str]:
    """Word timings must be monotonic and stay inside the segment window."""
    problems: list[str] = []
    prev_end = seg.start_s
    for j, w in enumerate(seg.words):
        wwhere = f"{where} word[{j}] {w.text!r}"
        if not (w.text and w.text.strip()):
            problems.append(f"{wwhere}: empty word text")
        if w.end_s <= w.start_s:
            problems.append(f"{wwhere}: end_s <= start_s")
        if w.start_s < seg.start_s - _EPS or w.end_s > seg.end_s + _EPS:
            problems.append(
                f"{wwhere}: [{w.start_s}, {w.end_s}] falls outside its segment "
                f"[{seg.start_s}, {seg.end_s}]")
        if w.start_s < prev_end - _EPS:
            problems.append(f"{wwhere}: overlaps the previous word (start {w.start_s} < {prev_end})")
        prev_end = w.end_s
    return problems


def _validate_caption_track(track, index: int, reel_duration: float,
                            seen_ids: set) -> list[str]:
    problems: list[str] = []
    where0 = f"caption_track[{index}] {track.track_id!r}"
    if track.track_id in seen_ids:
        problems.append(f"{where0}: duplicate caption track_id")
    seen_ids.add(track.track_id)
    if track.kind not in _CAPTION_KINDS:
        problems.append(f"{where0}: kind {track.kind!r} not in {_CAPTION_KINDS}")
    if track.animation.kind not in _ANIMATIONS:
        problems.append(f"{where0}: animation.kind {track.animation.kind!r} not in {_ANIMATIONS}")
    problems.extend(_validate_caption_style(track.style, where0))

    prev_end = 0.0
    for seg in track.segments:
        where = f"{where0} segment[{seg.index}] {seg.segment_id!r}"
        if not (seg.text and seg.text.strip()):
            problems.append(f"{where}: empty caption text")
        if seg.end_s <= seg.start_s:
            problems.append(f"{where}: end_s <= start_s ({seg.start_s}, {seg.end_s})")
        if seg.start_s < -_EPS:
            problems.append(f"{where}: negative start_s {seg.start_s}")
        # Monotonic, non-overlapping in absolute time.
        if seg.start_s < prev_end - _EPS:
            problems.append(
                f"{where}: not monotonic — starts {seg.start_s} before previous end {prev_end}")
        # Never exceed the audio/reel duration.
        if seg.end_s > reel_duration + _EPS:
            problems.append(
                f"{where}: end_s {seg.end_s} exceeds reel/audio duration {reel_duration}")
        # word/karaoke need per-word timings; validate any words present.
        if track.kind in ("word", "karaoke") and not seg.words:
            problems.append(f"{where}: {track.kind} captions require per-word timings")
        problems.extend(_validate_words(seg, where))
        prev_end = seg.end_s
    return problems


def validate_or_raise(tl: Timeline) -> Timeline:
    """Return ``tl`` if valid, else raise :class:`TimelineError` listing every
    problem at once (so the caller fixes them in one pass)."""
    problems = validate_timeline(tl)
    if problems:
        raise TimelineError("Timeline is not renderable", problems=problems)
    return tl
