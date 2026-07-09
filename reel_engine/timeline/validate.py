"""Timeline validation (Phase C2).

A Timeline must be *renderable* before any backend touches it: right schema,
even encoder-friendly dimensions, positive fps/durations, and at least one
solid background per scene. Validation returns a list of human-readable
problems (empty == valid); ``validate_or_raise`` turns a non-empty list into a
single :class:`TimelineError`. No renderer, no I/O — pure inspection.
"""
from __future__ import annotations

from foundation.exceptions import ConfigError
from reel_engine.interfaces.types import (
    ASSET_ANIMATIONS,
    ASSET_FITS,
    ASSET_KINDS,
    ASSET_LAYOUTS,
    ASSET_TRANSITIONS,
    AUDIO_FADE_CURVES,
    BRANDING_POSITIONS,
    TIMELINE_SCHEMA_VERSION,
    Clip,
    Timeline,
)


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

    # Branding is a native track timed in ABSOLUTE reel time (C5). Absent on
    # v1/v2 timelines, which skip this entirely.
    if tl.branding is not None:
        problems.extend(_validate_branding(tl.branding, reel_duration))

    # Visual-asset (B-roll) tracks (C6), also absolute reel time.
    asset_ids: set[str] = set()
    for i, track in enumerate(tl.asset_tracks):
        problems.extend(_validate_asset_track(track, i, reel_duration, asset_ids))

    # Music tracks (C8) — background beds mixed under the voice, absolute reel
    # time. Absent on v1..v4 timelines, which skip this entirely.
    music_ids: set[str] = set()
    for i, track in enumerate(tl.music_tracks):
        problems.extend(_validate_music_track(track, i, reel_duration, music_ids))

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


def _validate_theme(theme, where: str) -> list[str]:
    problems: list[str] = []
    for name in ("primary_color", "secondary_color", "text_color", "background_color"):
        if not _valid_rgb(getattr(theme, name)):
            problems.append(f"{where}: theme.{name} is not a valid RGB triple")
    if theme.logo_position not in BRANDING_POSITIONS:
        problems.append(f"{where}: theme.logo_position {theme.logo_position!r} not in {BRANDING_POSITIONS}")
    if not (0.0 < theme.logo_scale <= 1.0):
        problems.append(f"{where}: theme.logo_scale must be in (0, 1], got {theme.logo_scale}")
    for m in ("safe_margin_v", "safe_margin_h"):
        if not (0.0 <= getattr(theme, m) < 0.5):
            problems.append(f"{where}: theme.{m} must be in [0, 0.5), got {getattr(theme, m)}")
    for o in ("lower_third_opacity", "watermark_opacity"):
        if not (0.0 <= getattr(theme, o) <= 1.0):
            problems.append(f"{where}: theme.{o} must be in [0, 1], got {getattr(theme, o)}")
    for dfield in ("intro_duration_s", "outro_duration_s"):
        if getattr(theme, dfield) < 0:
            problems.append(f"{where}: theme.{dfield} must be non-negative")
    return problems


def _validate_overlay(el, where: str, reel_duration: float) -> list[str]:
    """Shared checks for logo/watermark: position, scale, opacity, time window."""
    problems: list[str] = []
    if el.position not in BRANDING_POSITIONS:
        problems.append(f"{where}: position {el.position!r} not in {BRANDING_POSITIONS}")
    if not (0.0 < el.scale <= 1.0):
        problems.append(f"{where}: scale must be in (0, 1], got {el.scale}")
    if not (0.0 <= el.opacity <= 1.0):
        problems.append(f"{where}: opacity must be in [0, 1], got {el.opacity}")
    if el.source is None and not (el.text and el.text.strip()):
        problems.append(f"{where}: needs an image source or non-empty text")
    s = el.start_s if el.start_s is not None else 0.0
    e = el.end_s if el.end_s is not None else reel_duration
    if e <= s:
        problems.append(f"{where}: end_s {e} <= start_s {s}")
    if s < -_EPS or e > reel_duration + _EPS:
        problems.append(f"{where}: window [{s}, {e}] outside reel [0, {reel_duration}]")
    return problems


def _validate_branding(track, reel_duration: float) -> list[str]:
    problems: list[str] = []
    where0 = f"branding {track.track_id!r}"
    problems.extend(_validate_theme(track.theme, where0))

    if track.logo is not None:
        problems.extend(_validate_overlay(track.logo, f"{where0} logo", reel_duration))
    if track.watermark is not None:
        problems.extend(_validate_overlay(track.watermark, f"{where0} watermark", reel_duration))

    intro_d = track.intro.duration_s if track.intro else 0.0
    outro_d = track.outro.duration_s if track.outro else 0.0
    if track.intro is not None:
        if not (track.intro.title and track.intro.title.strip()):
            problems.append(f"{where0} intro: empty title")
        if intro_d <= 0:
            problems.append(f"{where0} intro: duration_s must be positive, got {intro_d}")
        if intro_d > reel_duration + _EPS:
            problems.append(f"{where0} intro: duration {intro_d} exceeds reel {reel_duration}")
    if track.outro is not None:
        if not (track.outro.title and track.outro.title.strip()):
            problems.append(f"{where0} outro: empty title")
        if outro_d <= 0:
            problems.append(f"{where0} outro: duration_s must be positive, got {outro_d}")
        if outro_d > reel_duration + _EPS:
            problems.append(f"{where0} outro: duration {outro_d} exceeds reel {reel_duration}")
    # Intro and outro must not overlap (they bookend the reel).
    if intro_d + outro_d > reel_duration + _EPS:
        problems.append(
            f"{where0}: intro ({intro_d}s) + outro ({outro_d}s) exceed reel "
            f"duration ({reel_duration}s)")

    for i, lt in enumerate(track.lower_thirds):
        where = f"{where0} lower_third[{i}]"
        if not (lt.title and lt.title.strip()):
            problems.append(f"{where}: empty title")
        if lt.position not in BRANDING_POSITIONS:
            problems.append(f"{where}: position {lt.position!r} not in {BRANDING_POSITIONS}")
        if not (0.0 <= lt.opacity <= 1.0):
            problems.append(f"{where}: opacity must be in [0, 1], got {lt.opacity}")
        if lt.end_s <= lt.start_s:
            problems.append(f"{where}: end_s {lt.end_s} <= start_s {lt.start_s}")
        if lt.start_s < -_EPS or lt.end_s > reel_duration + _EPS:
            problems.append(
                f"{where}: window [{lt.start_s}, {lt.end_s}] outside reel "
                f"[0, {reel_duration}]")
    return problems


def _frac_rect(x, y, w, h, where: str, what: str) -> list[str]:
    """A rectangle given as fractions must sit inside the unit square."""
    problems: list[str] = []
    if w <= 0 or h <= 0:
        problems.append(f"{where}: {what} must have positive size, got w={w} h={h}")
    for name, v in (("x", x), ("y", y), ("w", w), ("h", h)):
        if v < -_EPS or v > 1.0 + _EPS:
            problems.append(f"{where}: {what}.{name} {v} outside [0, 1]")
    if x + w > 1.0 + _EPS or y + h > 1.0 + _EPS:
        problems.append(f"{where}: {what} [{x}, {y}, {w}, {h}] extends past the frame")
    return problems


def _validate_asset_clip(clip, where: str, reel_duration: float) -> list[str]:
    problems: list[str] = []
    if clip.kind not in ASSET_KINDS:
        problems.append(f"{where}: kind {clip.kind!r} not in {ASSET_KINDS}")
    if clip.source is None or not (clip.source.uri and str(clip.source.uri).strip()):
        problems.append(f"{where}: missing source asset (no file)")
    if clip.end_s <= clip.start_s:
        problems.append(f"{where}: end_s {clip.end_s} <= start_s {clip.start_s}")
    if clip.start_s < -_EPS or clip.end_s > reel_duration + _EPS:
        problems.append(
            f"{where}: window [{clip.start_s}, {clip.end_s}] outside reel "
            f"[0, {reel_duration}]")
    if not (0.0 <= clip.opacity <= 1.0):
        problems.append(f"{where}: opacity must be in [0, 1], got {clip.opacity}")
    if clip.layout.kind not in ASSET_LAYOUTS:
        problems.append(f"{where}: layout.kind {clip.layout.kind!r} not in {ASSET_LAYOUTS}")
    if not (0.0 < clip.layout.scale <= 1.0):
        problems.append(f"{where}: layout.scale must be in (0, 1], got {clip.layout.scale}")
    for anim, label in ((clip.animation_in, "animation_in"),
                        (clip.animation_out, "animation_out")):
        if anim.kind not in ASSET_ANIMATIONS:
            problems.append(f"{where}: {label}.kind {anim.kind!r} not in {ASSET_ANIMATIONS}")
        if anim.duration_s < 0:
            problems.append(f"{where}: {label}.duration_s must be non-negative")
    if clip.transition.kind not in ASSET_TRANSITIONS:
        problems.append(f"{where}: transition.kind {clip.transition.kind!r} "
                        f"not in {ASSET_TRANSITIONS}")
    if clip.placement is not None:
        p = clip.placement
        if p.fit not in ASSET_FITS:
            problems.append(f"{where}: placement.fit {p.fit!r} not in {ASSET_FITS}")
        problems.extend(_frac_rect(p.x, p.y, p.w, p.h, where, "placement"))
    problems.extend(_frac_rect(clip.crop.x, clip.crop.y, clip.crop.w, clip.crop.h,
                               where, "crop"))
    return problems


def _validate_asset_track(track, index: int, reel_duration: float,
                          seen_ids: set) -> list[str]:
    problems: list[str] = []
    where0 = f"asset_track[{index}] {track.track_id!r}"
    if track.track_id in seen_ids:
        problems.append(f"{where0}: duplicate asset track_id")
    seen_ids.add(track.track_id)
    clip_ids: set[str] = set()
    for clip in track.clips:
        where = f"{where0} clip {clip.clip_id!r}"
        if clip.clip_id in clip_ids:
            problems.append(f"{where}: duplicate clip_id")
        clip_ids.add(clip.clip_id)
        problems.extend(_validate_asset_clip(clip, where, reel_duration))
    return problems


def _validate_music_clip(clip, where: str, reel_duration: float) -> list[str]:
    problems: list[str] = []
    if clip.source is None or not (clip.source.uri and str(clip.source.uri).strip()):
        problems.append(f"{where}: missing source audio (no file)")
    if clip.end_s <= clip.start_s:
        problems.append(f"{where}: end_s {clip.end_s} <= start_s {clip.start_s}")
    if clip.start_s < -_EPS or clip.end_s > reel_duration + _EPS:
        problems.append(
            f"{where}: window [{clip.start_s}, {clip.end_s}] outside reel "
            f"[0, {reel_duration}]")
    if not (0.0 <= clip.gain <= 1.0):
        problems.append(f"{where}: gain must be in [0, 1], got {clip.gain}")
    if clip.source_offset_s < -_EPS:
        problems.append(f"{where}: source_offset_s must be non-negative, got {clip.source_offset_s}")
    # fade
    f = clip.fade
    if f.curve not in AUDIO_FADE_CURVES:
        problems.append(f"{where}: fade.curve {f.curve!r} not in {AUDIO_FADE_CURVES}")
    if f.fade_in_s < -_EPS or f.fade_out_s < -_EPS:
        problems.append(f"{where}: fade durations must be non-negative")
    if f.fade_in_s + f.fade_out_s > clip.duration_s + _EPS:
        problems.append(
            f"{where}: fades ({f.fade_in_s}+{f.fade_out_s}s) exceed clip duration "
            f"{clip.duration_s}s")
    # loop
    if clip.loop.crossfade_s < -_EPS:
        problems.append(f"{where}: loop.crossfade_s must be non-negative")
    # ducking
    dk = clip.ducking
    if not (0.0 <= dk.duck_level <= 1.0):
        problems.append(f"{where}: ducking.duck_level must be in [0, 1], got {dk.duck_level}")
    if dk.attack_s < -_EPS or dk.release_s < -_EPS or dk.pad_s < -_EPS:
        problems.append(f"{where}: ducking attack/release/pad must be non-negative")
    # envelope: breakpoints ascending in time, gains non-negative, inside window
    prev_t = None
    for j, pt in enumerate(clip.envelope.points):
        if not (isinstance(pt, (tuple, list)) and len(pt) == 2):
            problems.append(f"{where}: envelope point[{j}] must be (time_s, gain)")
            continue
        t, g = pt
        if g < -_EPS:
            problems.append(f"{where}: envelope point[{j}] gain {g} is negative")
        if prev_t is not None and t < prev_t - _EPS:
            problems.append(f"{where}: envelope point[{j}] time {t} not ascending")
        prev_t = t
    # mute sections: ordered, inside the clip window
    for j, sec in enumerate(clip.mute_sections):
        if not (isinstance(sec, (tuple, list)) and len(sec) == 2):
            problems.append(f"{where}: mute_section[{j}] must be (start_s, end_s)")
            continue
        s, e = sec
        if e <= s:
            problems.append(f"{where}: mute_section[{j}] end {e} <= start {s}")
        if s < clip.start_s - _EPS or e > clip.end_s + _EPS:
            problems.append(
                f"{where}: mute_section[{j}] [{s}, {e}] outside clip window "
                f"[{clip.start_s}, {clip.end_s}]")
    return problems


def _validate_music_track(track, index: int, reel_duration: float,
                          seen_ids: set) -> list[str]:
    problems: list[str] = []
    where0 = f"music_track[{index}] {track.track_id!r}"
    if track.track_id in seen_ids:
        problems.append(f"{where0}: duplicate music track_id")
    seen_ids.add(track.track_id)
    if track.gain < -_EPS:
        problems.append(f"{where0}: gain must be non-negative, got {track.gain}")
    clip_ids: set[str] = set()
    for clip in track.clips:
        where = f"{where0} clip {clip.clip_id!r}"
        if clip.clip_id in clip_ids:
            problems.append(f"{where}: duplicate clip_id")
        clip_ids.add(clip.clip_id)
        problems.extend(_validate_music_clip(clip, where, reel_duration))
    return problems


def validate_or_raise(tl: Timeline) -> Timeline:
    """Return ``tl`` if valid, else raise :class:`TimelineError` listing every
    problem at once (so the caller fixes them in one pass)."""
    problems = validate_timeline(tl)
    if problems:
        raise TimelineError("Timeline is not renderable", problems=problems)
    return tl
