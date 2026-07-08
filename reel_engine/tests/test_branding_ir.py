"""Branding Timeline IR tests (Phase C5).

Branding is a native Timeline track. These hermetic tests pin the frozen
dataclasses, serde round-trip, backward compatibility with v1/v2 timelines, and
the branding validation rules (positions, opacity/scale ranges, safe margins,
intro+outro fit, lower-third windows, explicit errors). No renderer, no ffmpeg.
"""
from __future__ import annotations

import dataclasses
import json

import pytest

from reel_engine.interfaces.types import (
    TIMELINE_SCHEMA_VERSION,
    AssetRef,
    BrandingTrack,
    Intro,
    Logo,
    LowerThird,
    Outro,
    Scene,
    Theme,
    Timeline,
    TimelineMeta,
    Watermark,
)
from reel_engine.timeline.hashing import timeline_content_hash
from reel_engine.timeline.serde import (
    timeline_from_dict,
    timeline_from_json,
    timeline_to_dict,
    timeline_to_json,
)
from reel_engine.timeline.validate import validate_timeline


def _scene(duration_s=10.0):
    return Scene.simple(0, (0, 0, 255), None, duration_s=duration_s)


def _branding(**over):
    base = dict(
        theme=Theme(name="corporate"),
        logo=Logo(source=AssetRef(kind="file", uri="/x/logo.png"), position="top_right"),
        watermark=Watermark(text="@creator", position="bottom_right", opacity=0.4),
        intro=Intro("My Channel", "Weekly tips", duration_s=2.0),
        outro=Outro("Thanks!", "Subscribe", duration_s=2.5, handles=("@ig", "site.com")),
        lower_thirds=(LowerThird("Jane Doe", "Founder", 0.5, 3.0),),
    )
    base.update(over)
    return BrandingTrack(**base)


def _timeline(branding, scene_duration=10.0):
    return Timeline(meta=TimelineMeta(width=1080, height=1920, fps=30),
                    scenes=(_scene(scene_duration),), branding=branding)


# ------------------------------------------------------------------ data model
def test_branding_dataclasses_are_immutable():
    b = _branding()
    for obj in (b, b.theme, b.logo, b.watermark, b.intro, b.outro, b.lower_thirds[0]):
        assert dataclasses.is_dataclass(obj)
        with pytest.raises(dataclasses.FrozenInstanceError):
            obj.name = "nope"


def test_schema_is_v3_and_has_branding():
    tl = _timeline(_branding())
    assert tl.schema_version == TIMELINE_SCHEMA_VERSION >= 3
    assert tl.has_branding
    assert not Timeline(scenes=(_scene(),)).has_branding
    assert not _timeline(BrandingTrack()).has_branding      # theme only, no elements


# --------------------------------------------------------------------- serde
def test_branding_serde_roundtrip_lossless():
    tl = _timeline(_branding())
    restored = timeline_from_json(timeline_to_json(tl))
    assert restored == tl
    assert timeline_content_hash(restored) == timeline_content_hash(tl)


def test_v2_timeline_without_branding_still_loads():
    d = timeline_to_dict(_timeline(_branding()))
    d.pop("branding")
    d["schema_version"] = 2
    tl = timeline_from_dict(d)
    assert tl.schema_version == 2 and tl.branding is None and not tl.has_branding


def test_theme_partial_serde_fills_defaults():
    tl = _timeline(BrandingTrack(theme=Theme(name="dark"), intro=Intro("Hi")))
    restored = timeline_from_json(timeline_to_json(tl))
    assert restored.branding.theme == Theme(name="dark")


# ------------------------------------------------------------------ validation
def test_valid_branding_has_no_problems():
    assert validate_timeline(_timeline(_branding())) == []


def test_intro_plus_outro_exceeding_reel_is_rejected():
    b = _branding(intro=Intro("a", duration_s=6.0), outro=Outro("b", duration_s=6.0))
    assert any("exceed reel" in p for p in validate_timeline(_timeline(b)))


def test_bad_positions_and_ranges_are_rejected():
    b = _branding(
        theme=Theme(logo_position="somewhere", safe_margin_v=0.9),
        logo=Logo(text="X", position="nowhere", scale=1.5, opacity=2.0),
    )
    problems = validate_timeline(_timeline(b))
    assert any("theme.logo_position" in p for p in problems)
    assert any("theme.safe_margin_v" in p for p in problems)
    assert any("logo: position" in p for p in problems)
    assert any("logo: scale" in p for p in problems)
    assert any("logo: opacity" in p for p in problems)


def test_overlay_without_source_or_text_is_rejected():
    b = _branding(logo=Logo())        # no source, no text
    assert any("image source or non-empty text" in p
               for p in validate_timeline(_timeline(b)))


def test_lower_third_window_outside_reel_is_rejected():
    b = _branding(lower_thirds=(LowerThird("Name", "", 8.0, 20.0),))
    assert any("outside reel" in p for p in validate_timeline(_timeline(b)))


def test_empty_intro_title_is_rejected():
    b = _branding(intro=Intro("   ", duration_s=1.0))
    assert any("intro: empty title" in p for p in validate_timeline(_timeline(b)))
