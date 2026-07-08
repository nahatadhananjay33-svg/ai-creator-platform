"""Reels Engine frozen-interface tests (Phase C2). Hermetic, pure Python."""
from __future__ import annotations

import dataclasses

import pytest

from reel_engine.interfaces import (
    AssetRef,
    Clip,
    Scene,
    Timeline,
    TimelineMeta,
    Track,
    Transition,
    aspect_ratio_string,
)


def test_value_types_are_frozen():
    scene = Scene.simple(0, (0, 0, 255), "Hi", 2.0)
    tl = Timeline(meta=TimelineMeta(), scenes=(scene,))
    for obj in (scene, tl, tl.meta, Transition(), AssetRef("color", "#000000")):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(obj, "scene_id" if isinstance(obj, Scene) else "kind", "x")


def test_scene_simple_builds_expected_tracks():
    scene = Scene.simple(1, (0, 128, 0), "Subtitle", 3.0)
    assert scene.scene_id == "scene-001" and scene.duration_s == 3.0
    assert {t.kind for t in scene.tracks} == {"background", "text", "audio"}
    assert scene.background_color() == (0, 128, 0)
    (txt,) = scene.text_clips()
    assert txt.kind == "text" and txt.text == "Subtitle"
    # background + audio clips span the whole scene
    bg = scene.track("background").clips[0]
    assert bg.kind == "solid_color" and bg.duration_s == 3.0


def test_scene_without_text_has_no_text_track():
    scene = Scene.simple(0, (0, 0, 0), None, 1.5)
    assert scene.track("text") is None
    assert scene.text_clips() == ()


def test_timeline_derived_duration_and_counts():
    scenes = [Scene.simple(i, (0, 0, 0), f"s{i}", 2.0) for i in range(3)]
    tl = Timeline(meta=TimelineMeta(), scenes=tuple(scenes))
    assert tl.n_scenes == 3
    assert tl.duration_s == 6.0


def test_collections_are_tuples_not_lists():
    scene = Scene.simple(0, (1, 2, 3), "x", 1.0)
    assert isinstance(scene.tracks, tuple)
    assert isinstance(scene.tracks[0].clips, tuple)


@pytest.mark.parametrize(
    "w,h,expected",
    [(1080, 1920, "9:16"), (1080, 1080, "1:1"), (1920, 1080, "16:9"),
     (1280, 720, "16:9"), (0, 5, "0:0")],
)
def test_aspect_ratio_string(w, h, expected):
    assert aspect_ratio_string(w, h) == expected


def test_clip_duration_property():
    c = Clip(clip_id="c", kind="text", start_s=1.0, end_s=3.5, text="x")
    assert c.duration_s == 2.5
