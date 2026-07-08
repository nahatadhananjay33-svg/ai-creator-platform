"""Timeline ⇄ JSON serialization (Phase C2).

Explicit encoders/decoders (not ``dataclasses.asdict``) so we fully control the
on-disk schema and round-trip types correctly: JSON has no tuples, so every
tuple (scenes, tracks, clips, colours) is written as a list and rebuilt as a
tuple on load. The result is a portable, diffable ``project.json`` — the anchor
for resumable/incremental rendering in later phases.
"""
from __future__ import annotations

import json
from typing import Any

from reel_engine.interfaces.types import (
    TIMELINE_SCHEMA_VERSION,
    AssetRef,
    CaptionAnimation,
    CaptionSegment,
    CaptionStyle,
    CaptionTrack,
    Clip,
    Scene,
    Timeline,
    TimelineMeta,
    Track,
    Transition,
    WordTiming,
)


# ------------------------------------------------------------------- encoders
def _asset_to_dict(a: AssetRef | None) -> dict[str, Any] | None:
    if a is None:
        return None
    return {"kind": a.kind, "uri": a.uri, "content_hash": a.content_hash,
            "meta": dict(a.meta)}


def _transition_to_dict(t: Transition) -> dict[str, Any]:
    return {"kind": t.kind, "duration_s": t.duration_s}


def _clip_to_dict(c: Clip) -> dict[str, Any]:
    return {
        "clip_id": c.clip_id, "kind": c.kind,
        "start_s": c.start_s, "end_s": c.end_s,
        "source": _asset_to_dict(c.source),
        "text": c.text, "color": list(c.color), "style": dict(c.style),
        "box": list(c.box) if c.box is not None else None,
        "keyframes": list(c.keyframes),
    }


def _track_to_dict(t: Track) -> dict[str, Any]:
    return {"track_id": t.track_id, "kind": t.kind,
            "clips": [_clip_to_dict(c) for c in t.clips]}


def _scene_to_dict(s: Scene) -> dict[str, Any]:
    return {
        "scene_id": s.scene_id, "index": s.index, "duration_s": s.duration_s,
        "tracks": [_track_to_dict(t) for t in s.tracks],
        "transition_in": _transition_to_dict(s.transition_in),
        "transition_out": _transition_to_dict(s.transition_out),
    }


def _meta_to_dict(m: TimelineMeta) -> dict[str, Any]:
    return {"title": m.title, "width": m.width, "height": m.height, "fps": m.fps,
            "background_default": list(m.background_default)}


# ---- captions (C4) ----
def _word_to_dict(w: WordTiming) -> dict[str, Any]:
    return {"text": w.text, "start_s": w.start_s, "end_s": w.end_s}


def _caption_style_to_dict(s: CaptionStyle) -> dict[str, Any]:
    return {
        "name": s.name, "font_family": s.font_family, "font_size": s.font_size,
        "primary_color": list(s.primary_color), "highlight_color": list(s.highlight_color),
        "outline_color": list(s.outline_color), "outline_width": s.outline_width,
        "shadow": s.shadow, "shadow_color": list(s.shadow_color),
        "shadow_offset": s.shadow_offset, "box": s.box, "box_color": list(s.box_color),
        "box_opacity": s.box_opacity, "alignment": s.alignment, "position": s.position,
        "safe_margin_v": s.safe_margin_v, "safe_margin_h": s.safe_margin_h,
        "max_chars_per_line": s.max_chars_per_line, "uppercase": s.uppercase, "bold": s.bold,
    }


def _caption_animation_to_dict(a: CaptionAnimation) -> dict[str, Any]:
    return {"kind": a.kind, "duration_s": a.duration_s}


def _caption_segment_to_dict(s: CaptionSegment) -> dict[str, Any]:
    return {
        "segment_id": s.segment_id, "index": s.index, "text": s.text,
        "start_s": s.start_s, "end_s": s.end_s,
        "words": [_word_to_dict(w) for w in s.words],
    }


def _caption_track_to_dict(t: CaptionTrack) -> dict[str, Any]:
    return {
        "track_id": t.track_id, "kind": t.kind,
        "segments": [_caption_segment_to_dict(s) for s in t.segments],
        "style": _caption_style_to_dict(t.style),
        "animation": _caption_animation_to_dict(t.animation),
    }


def timeline_to_dict(tl: Timeline) -> dict[str, Any]:
    """Plain JSON-able mapping for a Timeline (stable field order)."""
    return {
        "schema_version": tl.schema_version,
        "meta": _meta_to_dict(tl.meta),
        "scenes": [_scene_to_dict(s) for s in tl.scenes],
        "caption_tracks": [_caption_track_to_dict(t) for t in tl.caption_tracks],
    }


def timeline_to_json(tl: Timeline, *, indent: int | None = 2) -> str:
    return json.dumps(timeline_to_dict(tl), ensure_ascii=False, indent=indent,
                      sort_keys=True)


# ------------------------------------------------------------------- decoders
def _asset_from_dict(d: dict[str, Any] | None) -> AssetRef | None:
    if d is None:
        return None
    return AssetRef(kind=d["kind"], uri=d["uri"],
                    content_hash=d.get("content_hash"), meta=dict(d.get("meta", {})))


def _transition_from_dict(d: dict[str, Any] | None) -> Transition:
    if not d:
        return Transition()
    return Transition(kind=d.get("kind", "cut"), duration_s=d.get("duration_s", 0.0))


def _clip_from_dict(d: dict[str, Any]) -> Clip:
    box = d.get("box")
    return Clip(
        clip_id=d["clip_id"], kind=d["kind"],
        start_s=d.get("start_s", 0.0), end_s=d.get("end_s", 0.0),
        source=_asset_from_dict(d.get("source")),
        text=d.get("text"), color=tuple(d.get("color", (0, 0, 0))),
        style=dict(d.get("style", {})),
        box=tuple(box) if box is not None else None,
        keyframes=tuple(tuple(k) if isinstance(k, list) else k
                        for k in d.get("keyframes", ())),
    )


def _track_from_dict(d: dict[str, Any]) -> Track:
    return Track(track_id=d["track_id"], kind=d["kind"],
                 clips=tuple(_clip_from_dict(c) for c in d.get("clips", ())))


def _scene_from_dict(d: dict[str, Any]) -> Scene:
    return Scene(
        scene_id=d["scene_id"], index=d["index"], duration_s=d["duration_s"],
        tracks=tuple(_track_from_dict(t) for t in d.get("tracks", ())),
        transition_in=_transition_from_dict(d.get("transition_in")),
        transition_out=_transition_from_dict(d.get("transition_out")),
    )


def _meta_from_dict(d: dict[str, Any]) -> TimelineMeta:
    return TimelineMeta(
        title=d.get("title", "untitled"),
        width=d.get("width", 1080), height=d.get("height", 1920),
        fps=d.get("fps", 30),
        background_default=tuple(d.get("background_default", (0, 0, 0))),
    )


# ---- captions (C4) ----
def _word_from_dict(d: dict[str, Any]) -> WordTiming:
    return WordTiming(text=d["text"], start_s=d["start_s"], end_s=d["end_s"])


def _caption_style_from_dict(d: dict[str, Any] | None) -> CaptionStyle:
    if not d:
        return CaptionStyle()
    defaults = CaptionStyle()
    tuple_fields = ("primary_color", "highlight_color", "outline_color",
                    "shadow_color", "box_color")
    kwargs: dict[str, Any] = {}
    for f in _caption_style_to_dict(defaults):
        if f in d:
            kwargs[f] = tuple(d[f]) if f in tuple_fields else d[f]
    return CaptionStyle(**kwargs)


def _caption_animation_from_dict(d: dict[str, Any] | None) -> CaptionAnimation:
    if not d:
        return CaptionAnimation()
    return CaptionAnimation(kind=d.get("kind", "none"), duration_s=d.get("duration_s", 0.2))


def _caption_segment_from_dict(d: dict[str, Any]) -> CaptionSegment:
    return CaptionSegment(
        segment_id=d["segment_id"], index=d["index"], text=d["text"],
        start_s=d["start_s"], end_s=d["end_s"],
        words=tuple(_word_from_dict(w) for w in d.get("words", ())),
    )


def _caption_track_from_dict(d: dict[str, Any]) -> CaptionTrack:
    return CaptionTrack(
        track_id=d["track_id"], kind=d.get("kind", "sentence"),
        segments=tuple(_caption_segment_from_dict(s) for s in d.get("segments", ())),
        style=_caption_style_from_dict(d.get("style")),
        animation=_caption_animation_from_dict(d.get("animation")),
    )


def timeline_from_dict(d: dict[str, Any]) -> Timeline:
    """Rebuild a Timeline from a mapping. Rejects unknown future schema
    versions loudly rather than silently mis-parsing. ``caption_tracks`` is
    optional so v1 projects (no captions) load unchanged."""
    version = d.get("schema_version", TIMELINE_SCHEMA_VERSION)
    if version > TIMELINE_SCHEMA_VERSION:
        raise ValueError(
            f"Timeline schema_version {version} is newer than this build "
            f"supports ({TIMELINE_SCHEMA_VERSION}); upgrade reel_engine."
        )
    return Timeline(
        meta=_meta_from_dict(d.get("meta", {})),
        scenes=tuple(_scene_from_dict(s) for s in d.get("scenes", ())),
        caption_tracks=tuple(_caption_track_from_dict(t)
                             for t in d.get("caption_tracks", ())),
        schema_version=version,
    )


def timeline_from_json(text: str) -> Timeline:
    return timeline_from_dict(json.loads(text))
