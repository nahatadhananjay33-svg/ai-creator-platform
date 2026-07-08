"""Timeline construction + validation tests (Phase C2). Hermetic."""
from __future__ import annotations

import pytest

from reel_engine.interfaces import Scene, Timeline, TimelineMeta, Track
from reel_engine.timeline import (
    TimelineError,
    build_demo_timeline,
    new_timeline,
    storyboard,
    validate_or_raise,
    validate_timeline,
)


def test_demo_timeline_is_valid_blue_green_red():
    tl = build_demo_timeline()
    assert tl.n_scenes == 3
    assert [s.background_color() for s in tl.scenes] == [(0, 0, 255), (0, 128, 0), (255, 0, 0)]
    assert [s.text_clips()[0].text for s in tl.scenes] == ["Title", "Subtitle", "Call To Action"]
    assert tl.meta.aspect == "9:16"
    assert validate_timeline(tl) == []


def test_storyboard_accepts_named_and_rgb_colors():
    tl = storyboard([("blue", "A", 1.0), ((10, 20, 30), "B", 2.0)])
    assert tl.scenes[0].background_color() == (0, 0, 255)
    assert tl.scenes[1].background_color() == (10, 20, 30)
    assert tl.duration_s == 3.0


def test_validation_flags_empty_timeline():
    problems = validate_timeline(Timeline(meta=TimelineMeta(), scenes=()))
    assert any("no scenes" in p for p in problems)


def test_validation_flags_odd_dimensions():
    tl = Timeline(meta=TimelineMeta(width=1081, height=1920),
                  scenes=(Scene.simple(0, (0, 0, 0), "x", 1.0),))
    assert any("even dimensions" in p for p in validate_timeline(tl))


def test_validation_flags_nonpositive_duration_and_missing_background():
    bad_scene = Scene(scene_id="s", index=0, duration_s=0.0, tracks=())
    problems = validate_timeline(
        Timeline(meta=TimelineMeta(), scenes=(bad_scene,))
    )
    assert any("duration_s must be positive" in p for p in problems)
    assert any("no background" in p for p in problems)


def test_validation_flags_empty_text_clip():
    from reel_engine.interfaces import Clip
    scene = Scene(
        scene_id="s", index=0, duration_s=2.0,
        tracks=(
            Track("bg", "background", (Clip("c", "solid_color", 0, 2.0, color=(0, 0, 0)),)),
            Track("t", "text", (Clip("tc", "text", 0, 2.0, text="  "),)),
        ),
    )
    assert any("empty text" in p for p in validate_timeline(scene_timeline(scene)))


def scene_timeline(scene: Scene) -> Timeline:
    return Timeline(meta=TimelineMeta(), scenes=(scene,))


def test_new_timeline_validates_by_default():
    with pytest.raises(TimelineError):
        new_timeline([Scene(scene_id="s", index=0, duration_s=-1.0, tracks=())])


def test_validate_or_raise_returns_timeline_when_ok():
    tl = build_demo_timeline()
    assert validate_or_raise(tl) is tl
