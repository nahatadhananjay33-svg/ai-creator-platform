"""Subtitle export tests (Phase C4) — SRT / WebVTT / JSON / Timeline captions.

Hermetic and deterministic: fixed caption tracks in, exact strings out.
"""
from __future__ import annotations

import json

from reel_engine.interfaces.types import (
    CaptionSegment,
    CaptionTrack,
    WordTiming,
)
from reel_engine.timeline.serde import _caption_track_from_dict

from caption_engine.export import (
    to_json,
    to_srt,
    to_timeline_captions,
    to_webvtt,
    write_subtitles,
)
from caption_engine.export.subtitles import _fmt_timestamp


def _track():
    s0 = CaptionSegment("seg-000", 0, "Hello world", 0.0, 1.5,
                        words=(WordTiming("Hello", 0.0, 0.8), WordTiming("world", 0.8, 1.5)))
    s1 = CaptionSegment("seg-001", 1, "Second line", 1.5, 3.0,
                        words=(WordTiming("Second", 1.5, 2.3), WordTiming("line", 2.3, 3.0)))
    return CaptionTrack("captions", kind="karaoke", segments=(s0, s1))


# ------------------------------------------------------------------ timestamps
def test_timestamp_formatting():
    assert _fmt_timestamp(0.0, ",") == "00:00:00,000"
    assert _fmt_timestamp(3661.5, ",") == "01:01:01,500"
    assert _fmt_timestamp(1.667, ".") == "00:00:01.667"
    assert _fmt_timestamp(-1.0, ",") == "00:00:00,000"   # clamped


# -------------------------------------------------------------------- SRT / VTT
def test_srt_structure():
    srt = to_srt(_track())
    assert srt.startswith("1\n00:00:00,000 --> 00:00:01,500\nHello world\n")
    assert "2\n00:00:01,500 --> 00:00:03,000\nSecond line\n" in srt


def test_webvtt_has_header_and_dot_millis():
    vtt = to_webvtt(_track())
    assert vtt.startswith("WEBVTT\n")
    assert "00:00:00.000 --> 00:00:01.500" in vtt
    assert "Hello world" in vtt


def test_word_level_export_emits_one_cue_per_word():
    srt = to_srt(_track(), word_level=True)
    # 4 words -> 4 cues
    assert srt.count("-->") == 4
    assert "Hello" in srt and "world" in srt and "Second" in srt and "line" in srt


# --------------------------------------------------------------------- JSON
def test_json_export_is_structured_and_sorted():
    payload = json.loads(to_json(_track()))
    assert payload["kind"] == "karaoke"
    assert payload["track_id"] == "captions"
    assert len(payload["segments"]) == 2
    assert payload["segments"][0]["words"][0] == {
        "text": "Hello", "start_s": 0.0, "end_s": 0.8}


def test_timeline_captions_roundtrips_losslessly():
    track = _track()
    restored = _caption_track_from_dict(json.loads(to_timeline_captions(track)))
    assert restored == track


# -------------------------------------------------------------- write to disk
def test_write_subtitles_emits_all_four_files(tmp_path):
    paths = write_subtitles(_track(), tmp_path, stem="reel")
    assert set(paths) == {"srt", "vtt", "json", "timeline"}
    assert paths["srt"].name == "reel.srt"
    assert paths["timeline"].name == "reel.captions.json"
    for p in paths.values():
        assert p.exists() and p.stat().st_size > 0
    # deterministic: re-writing yields identical bytes
    before = {k: v.read_bytes() for k, v in paths.items()}
    again = write_subtitles(_track(), tmp_path, stem="reel")
    assert {k: v.read_bytes() for k, v in again.items()} == before


def test_empty_track_exports_are_valid():
    empty = CaptionTrack("captions", segments=())
    assert to_srt(empty) == ""
    assert to_webvtt(empty).startswith("WEBVTT")
    assert json.loads(to_json(empty))["segments"] == []
