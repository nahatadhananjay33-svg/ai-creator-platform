"""Music Timeline IR tests (Phase C8).

Music is a native Timeline track. These hermetic tests pin the frozen dataclasses,
serde round-trip, backward compatibility with v1..v4 timelines, and the music
validation rules (source presence, windows, gain, fades, loop, ducking, envelope
ordering, mute sections). No renderer, no ffmpeg.
"""
from __future__ import annotations

import dataclasses
import json

import pytest

from reel_engine.interfaces.types import (
    TIMELINE_SCHEMA_VERSION,
    AssetRef,
    AudioEnvelope,
    AudioFade,
    DuckingRule,
    LoopRule,
    MusicClip,
    MusicTrack,
    Scene,
    Timeline,
)
from reel_engine.timeline.hashing import timeline_content_hash
from reel_engine.timeline.serde import (
    timeline_from_dict,
    timeline_from_json,
    timeline_to_dict,
    timeline_to_json,
)
from reel_engine.timeline.validate import validate_timeline

DUR = 12.0


def _bed(uri="/x/bed.wav"):
    return AssetRef(kind="file", uri=uri)


def _clip(**over):
    base = dict(clip_id="m0", source=_bed(), start_s=0.0, end_s=DUR, gain=0.2,
                fade=AudioFade(1.0, 1.5), envelope=AudioEnvelope(((0.0, 1.0), (6.0, 0.5), (12.0, 1.0))),
                loop=LoopRule(True, 0.5), ducking=DuckingRule(True, 0.3, 0.2, 0.5),
                mute_sections=((2.0, 3.0),))
    base.update(over)
    return MusicClip(**base)


def _tl(track=None, dur=DUR, **over):
    tracks = (track,) if track is not None else (MusicTrack(clips=(_clip(),)),)
    return Timeline(scenes=(Scene.simple(0, (0, 0, 255), "x", duration_s=dur),),
                    music_tracks=tracks, **over)


# ---------------------------------------------------------------- IR + schema
def test_schema_version_supports_music_and_has_music():
    tl = _tl()
    assert tl.schema_version == TIMELINE_SCHEMA_VERSION >= 5
    assert tl.has_music
    assert tl.music_tracks[0].n_clips == 1
    assert tl.music_tracks[0].duration_s == DUR


def test_clip_and_track_are_immutable():
    clip = _clip()
    with pytest.raises(dataclasses.FrozenInstanceError):
        clip.gain = 0.9


def test_empty_track_has_no_music():
    assert not Timeline(scenes=(Scene.simple(0, (0, 0, 255), "x", duration_s=DUR),),
                        music_tracks=(MusicTrack(),)).has_music


# ------------------------------------------------------------------- serde
def test_serde_round_trip_and_hash_stable():
    tl = _tl()
    tl2 = timeline_from_json(timeline_to_json(tl))
    assert tl2.music_tracks[0].clips[0] == _clip()
    assert timeline_content_hash(tl) == timeline_content_hash(tl2)


def test_serde_preserves_all_music_fields():
    d = timeline_to_dict(_tl())["music_tracks"][0]["clips"][0]
    assert d["gain"] == 0.2 and d["fade"]["fade_in_s"] == 1.0
    assert d["envelope"]["points"] == [[0.0, 1.0], [6.0, 0.5], [12.0, 1.0]]
    assert d["loop"]["crossfade_s"] == 0.5 and d["ducking"]["duck_level"] == 0.3
    assert d["mute_sections"] == [[2.0, 3.0]]


def test_music_key_absent_when_no_music():
    d = timeline_to_dict(Timeline(scenes=(Scene.simple(0, (0, 0, 255), "x", duration_s=DUR),)))
    assert "music_tracks" not in d


def test_backward_compat_v4_timeline_loads_without_music():
    d = timeline_to_dict(_tl())
    d["schema_version"] = 4
    d.pop("music_tracks")
    tl = timeline_from_dict(d)
    assert tl.schema_version == 4 and tl.music_tracks == () and not tl.has_music


def test_loader_rejects_future_schema_version():
    d = timeline_to_dict(_tl())
    d["schema_version"] = TIMELINE_SCHEMA_VERSION + 1
    with pytest.raises(ValueError):
        timeline_from_dict(d)


# ---------------------------------------------------------------- validation
def test_valid_music_timeline_has_no_problems():
    assert validate_timeline(_tl()) == []


@pytest.mark.parametrize("over,needle", [
    (dict(source=None), "missing source"),
    (dict(start_s=5.0, end_s=2.0), "end_s"),
    (dict(end_s=DUR + 5), "outside reel"),
    (dict(gain=1.5), "gain must be in [0, 1]"),
    (dict(fade=AudioFade(10.0, 10.0)), "fades"),
    (dict(ducking=DuckingRule(True, 2.0)), "duck_level must be in [0, 1]"),
    (dict(envelope=AudioEnvelope(((5.0, 1.0), (1.0, 0.5)))), "not ascending"),
    (dict(mute_sections=((5.0, 20.0),)), "outside clip window"),
    (dict(source_offset_s=-1.0), "source_offset_s"),
])
def test_music_validation_flags_bad_clips(over, needle):
    problems = validate_timeline(_tl(MusicTrack(clips=(_clip(**over),))))
    assert any(needle in p for p in problems), (needle, problems)


def test_duplicate_music_clip_ids_flagged():
    track = MusicTrack(clips=(_clip(clip_id="dup"), _clip(clip_id="dup")))
    assert any("duplicate clip_id" in p for p in validate_timeline(_tl(track)))
