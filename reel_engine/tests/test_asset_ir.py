"""Visual-asset Timeline IR tests (Phase C6).

Visual assets (B-roll) are a native Timeline track. These hermetic tests pin the
frozen dataclasses, serde round-trip, backward compatibility with v1..v3
timelines, and the asset validation rules (kind, source presence, windows,
placement/crop rectangles, opacity/animation/transition, explicit errors).
No renderer, no ffmpeg.
"""
from __future__ import annotations

import dataclasses
import json

import pytest

from reel_engine.interfaces.types import (
    TIMELINE_SCHEMA_VERSION,
    AssetAnimation,
    AssetClip,
    AssetCrop,
    AssetLayout,
    AssetPlacement,
    AssetRef,
    AssetTrack,
    AssetTransition,
    Scene,
    Timeline,
    TimelineMeta,
)
from reel_engine.timeline.hashing import timeline_content_hash
from reel_engine.timeline.serde import (
    timeline_from_dict,
    timeline_from_json,
    timeline_to_dict,
    timeline_to_json,
)
from reel_engine.timeline.validate import validate_timeline

DUR = 10.0


def _img(uri="/x/img.png"):
    return AssetRef(kind="file", uri=uri)


def _clip(**over):
    base = dict(clip_id="a0", kind="image", source=_img(), start_s=1.0, end_s=4.0,
                layout=AssetLayout(kind="picture_in_picture", corner="top_right"),
                crop=AssetCrop(0.1, 0.1, 0.8, 0.8),
                animation_in=AssetAnimation("fade_in", 0.4),
                animation_out=AssetAnimation("fade_out", 0.4),
                transition=AssetTransition("cross_dissolve", 0.5),
                opacity=0.9, z_index=2)
    base.update(over)
    return AssetClip(**base)


def _timeline(track, scene_duration=DUR):
    return Timeline(meta=TimelineMeta(width=1080, height=1920, fps=30),
                    scenes=(Scene.simple(0, (0, 0, 255), None, duration_s=scene_duration),),
                    asset_tracks=(track,))


def _track(*clips):
    return AssetTrack("assets", clips=tuple(clips))


# ------------------------------------------------------------------ data model
def test_asset_dataclasses_are_immutable_and_derive():
    c = _clip()
    assert c.duration_s == 3.0 and not c.is_video
    assert AssetClip("v", kind="video", source=_img("/x/b.mp4"), start_s=0, end_s=1).is_video
    for obj in (c, c.layout, c.crop, c.animation_in, c.transition):
        assert dataclasses.is_dataclass(obj)
        with pytest.raises(dataclasses.FrozenInstanceError):
            obj.kind = "x"


def test_schema_is_v4_and_has_assets():
    tl = _timeline(_track(_clip()))
    assert tl.schema_version == TIMELINE_SCHEMA_VERSION >= 4
    assert tl.has_assets
    assert not Timeline(scenes=(Scene.simple(0, (0, 0, 0), None, 3.0),)).has_assets
    assert not _timeline(AssetTrack()).has_assets


# --------------------------------------------------------------------- serde
def test_asset_serde_roundtrip_lossless():
    tl = _timeline(_track(_clip(), _clip(clip_id="a1", kind="video",
                                         source=_img("/x/b.mp4"), start_s=4.0, end_s=8.0,
                                         placement=AssetPlacement(0.5, 0, 0.5, 1, "cover"))))
    restored = timeline_from_json(timeline_to_json(tl))
    assert restored == tl
    assert timeline_content_hash(restored) == timeline_content_hash(tl)


def test_v3_timeline_without_assets_still_loads():
    d = timeline_to_dict(_timeline(_track(_clip())))
    d.pop("asset_tracks")
    d["schema_version"] = 3
    tl = timeline_from_dict(d)
    assert tl.schema_version == 3 and tl.asset_tracks == () and not tl.has_assets


def test_placement_optional_defaults_to_none():
    restored = timeline_from_json(timeline_to_json(_timeline(_track(_clip()))))
    assert restored.asset_tracks[0].clips[0].placement is None


# ------------------------------------------------------------------ validation
def test_valid_asset_track_has_no_problems():
    assert validate_timeline(_timeline(_track(_clip()))) == []


def test_missing_source_is_rejected():
    assert any("missing source" in p
               for p in validate_timeline(_timeline(_track(_clip(source=None)))))


def test_window_outside_reel_is_rejected():
    assert any("outside reel" in p
               for p in validate_timeline(_timeline(_track(_clip(start_s=0.0, end_s=20.0)))))


def test_bad_kind_layout_and_ranges_are_rejected():
    bad = _clip(kind="hologram", opacity=2.0,
                layout=AssetLayout(kind="orbit"),
                animation_in=AssetAnimation("zoom_blur"))
    problems = validate_timeline(_timeline(_track(bad)))
    assert any("kind 'hologram'" in p for p in problems)
    assert any("layout.kind 'orbit'" in p for p in problems)
    assert any("opacity" in p for p in problems)
    assert any("animation_in.kind 'zoom_blur'" in p for p in problems)


def test_placement_and_crop_rectangles_are_bounds_checked():
    bad = _clip(placement=AssetPlacement(0.7, 0.0, 0.6, 1.0, "warp"),
                crop=AssetCrop(0.0, 0.0, 1.5, 1.0))
    problems = validate_timeline(_timeline(_track(bad)))
    assert any("placement.fit 'warp'" in p for p in problems)
    assert any("placement [0.7" in p and "past the frame" in p for p in problems)
    assert any("crop.w 1.5 outside" in p for p in problems)


def test_duplicate_clip_id_is_rejected():
    problems = validate_timeline(_timeline(_track(_clip(), _clip())))
    assert any("duplicate clip_id" in p for p in problems)
