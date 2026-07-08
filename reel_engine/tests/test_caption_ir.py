"""Caption Timeline IR tests (Phase C4).

Captions are a native Timeline track. These hermetic tests pin the frozen
dataclasses, serde round-trip, backward compatibility with v1 timelines, and the
synchronization validation rules (monotonic, within audio duration, word timings
inside their segment, explicit errors). No renderer, no ffmpeg, no models.
"""
from __future__ import annotations

from reel_engine.interfaces.types import (
    CaptionAnimation,
    CaptionSegment,
    CaptionStyle,
    CaptionTrack,
    Scene,
    Timeline,
    TimelineMeta,
    WordTiming,
)
from reel_engine.timeline.serde import (
    timeline_from_dict,
    timeline_from_json,
    timeline_to_dict,
    timeline_to_json,
)
from reel_engine.timeline.hashing import timeline_content_hash
from reel_engine.timeline.validate import validate_timeline


def _scene(duration_s=4.0):
    return Scene.simple(0, (0, 0, 255), "Hi", duration_s=duration_s)


def _words(pairs):
    return tuple(WordTiming(t, a, b) for t, a, b in pairs)


def _karaoke_track(track_id="cap0"):
    seg0 = CaptionSegment("s0", 0, "hello world", 0.0, 2.0,
                          words=_words([("hello", 0.0, 1.0), ("world", 1.0, 2.0)]))
    seg1 = CaptionSegment("s1", 1, "second line", 2.0, 4.0,
                          words=_words([("second", 2.0, 3.0), ("line", 3.0, 4.0)]))
    return CaptionTrack(track_id, kind="karaoke", segments=(seg0, seg1),
                        style=CaptionStyle(name="tiktok", position="center"),
                        animation=CaptionAnimation("pop", 0.15))


def _timeline(track, scene_duration=4.0):
    return Timeline(meta=TimelineMeta(width=1080, height=1920, fps=30),
                    scenes=(_scene(scene_duration),), caption_tracks=(track,))


# ------------------------------------------------------------------ data model
def test_caption_dataclasses_are_immutable_and_derive_durations():
    seg = CaptionSegment("s", 0, "hi there", 1.0, 3.5,
                         words=_words([("hi", 1.0, 2.0), ("there", 2.0, 3.5)]))
    assert seg.duration_s == 2.5 and seg.has_word_timings
    track = _karaoke_track()
    assert track.n_segments == 2 and track.duration_s == 4.0
    assert tuple(w.text for w in track.words()) == ("hello", "world", "second", "line")
    import dataclasses
    import pytest
    for obj in (seg, track, track.style, track.animation, seg.words[0]):
        assert dataclasses.is_dataclass(obj)
        with pytest.raises(dataclasses.FrozenInstanceError):
            obj.index = 99   # every caption type is frozen — no in-place mutation


def test_schema_version_supports_captions_and_has_captions():
    from reel_engine.interfaces.types import TIMELINE_SCHEMA_VERSION
    tl = _timeline(_karaoke_track())
    assert tl.schema_version == TIMELINE_SCHEMA_VERSION >= 2   # captions since v2
    assert tl.has_captions
    assert not Timeline(scenes=(_scene(),)).has_captions


# --------------------------------------------------------------------- serde
def test_caption_timeline_serde_roundtrip_lossless():
    tl = _timeline(_karaoke_track())
    restored = timeline_from_json(timeline_to_json(tl))
    assert restored == tl
    assert timeline_to_dict(restored) == timeline_to_dict(tl)
    assert timeline_content_hash(restored) == timeline_content_hash(tl)


def test_v1_timeline_without_captions_still_loads():
    # A schema v1 project (no caption_tracks key) must load unchanged.
    v1 = {
        "schema_version": 1,
        "meta": {"title": "old", "width": 1080, "height": 1920, "fps": 30,
                 "background_default": [0, 0, 0]},
        "scenes": timeline_to_dict(_timeline(_karaoke_track()))["scenes"],
    }
    tl = timeline_from_dict(v1)
    assert tl.schema_version == 1
    assert tl.caption_tracks == ()
    assert not tl.has_captions


def test_style_partial_serde_defaults_fill_missing():
    tl = _timeline(CaptionTrack("c", segments=(
        CaptionSegment("s", 0, "hi", 0.0, 1.0),)))
    restored = timeline_from_json(timeline_to_json(tl))
    assert restored.caption_tracks[0].style == CaptionStyle()


# ------------------------------------------------------------------ validation
def test_valid_caption_track_has_no_problems():
    assert validate_timeline(_timeline(_karaoke_track())) == []


def test_caption_exceeding_audio_duration_is_rejected():
    track = CaptionTrack("c", kind="sentence",
                         segments=(CaptionSegment("s", 0, "too long", 0.0, 6.0),))
    problems = validate_timeline(_timeline(track, scene_duration=4.0))
    assert any("exceeds reel/audio duration" in p for p in problems)


def test_non_monotonic_captions_are_rejected():
    track = CaptionTrack("c", kind="sentence", segments=(
        CaptionSegment("s0", 0, "first", 0.0, 2.0),
        CaptionSegment("s1", 1, "overlap", 1.5, 3.0)))   # starts before s0 ends
    problems = validate_timeline(_timeline(track))
    assert any("not monotonic" in p for p in problems)


def test_word_outside_segment_is_rejected():
    seg = CaptionSegment("s", 0, "hi", 0.0, 2.0,
                         words=_words([("hi", 0.0, 2.5)]))   # word ends after segment
    problems = validate_timeline(_timeline(CaptionTrack("c", kind="word", segments=(seg,))))
    assert any("outside its segment" in p for p in problems)


def test_word_karaoke_requires_word_timings():
    seg = CaptionSegment("s", 0, "no words here", 0.0, 2.0)   # no per-word timings
    problems = validate_timeline(_timeline(CaptionTrack("c", kind="word", segments=(seg,))))
    assert any("require per-word timings" in p for p in problems)


def test_bad_style_and_kind_are_rejected():
    bad = CaptionTrack("c", kind="bogus", segments=(
        CaptionSegment("s", 0, "x", 0.0, 1.0),),
        style=CaptionStyle(alignment="sideways", position="middle",
                           safe_margin_v=0.9))
    problems = validate_timeline(_timeline(bad))
    assert any("kind 'bogus'" in p for p in problems)
    assert any("alignment 'sideways'" in p for p in problems)
    assert any("position 'middle'" in p for p in problems)
    assert any("safe_margin_v" in p for p in problems)


def test_empty_caption_text_is_rejected():
    track = CaptionTrack("c", segments=(CaptionSegment("s", 0, "   ", 0.0, 1.0),))
    assert any("empty caption text" in p for p in validate_timeline(_timeline(track)))
