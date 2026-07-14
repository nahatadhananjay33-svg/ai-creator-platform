"""VAD region detection and 5-20 s segment planning."""
from __future__ import annotations

import numpy as np

from production.segment_dataset.config import V4Config
from production.segment_dataset.vad import (frame_levels, plan_segments,
                                            speech_regions)

from .conftest import SR, quiet, speech_with_pauses, tone

CFG = V4Config()


def _regions_s(x):
    dbfs, _, frame_dur = frame_levels(x, SR, CFG)
    regions = speech_regions(dbfs, frame_dur, CFG)
    return [(round(s * frame_dur, 1), round(e * frame_dur, 1)) for s, e in regions], \
        dbfs, frame_dur


def test_vad_finds_speech_and_ignores_long_pauses():
    # 6 s speech, 2 s pause (long), 8 s speech, trailing silence
    x = speech_with_pauses([("v", 6), ("s", 2), ("v", 8), ("s", 3)])
    regions, _, _ = _regions_s(x)
    assert len(regions) == 2
    (s1, e1), (s2, e2) = regions
    assert abs(s1 - 0.0) < 0.3 and abs(e1 - 6.0) < 0.3
    assert abs(s2 - 8.0) < 0.3 and abs(e2 - 16.0) < 0.3


def test_vad_bridges_short_pauses():
    # 3 s speech, 0.3 s breath pause, 3 s speech -> ONE region
    x = speech_with_pauses([("v", 3), ("s", 0.3), ("v", 3)])
    regions, _, _ = _regions_s(x)
    assert len(regions) == 1


def test_vad_silence_only_yields_nothing():
    regions, _, _ = _regions_s(quiet(10))
    assert regions == []


def test_segments_within_target_band_and_split_at_pause():
    # 30 s region with a soft pause at 12 s: split should land near it
    x = speech_with_pauses([("v", 12), ("s", 0.35), ("v", 18)])
    dbfs, _, frame_dur = frame_levels(x, SR, CFG)
    regions = speech_regions(dbfs, frame_dur, CFG)
    segs = plan_segments(regions, dbfs, frame_dur, x.size / SR, CFG)

    assert all(CFG.min_segment_s - 0.5 <= s.duration <= CFG.max_segment_s * 1.1 + 0.5
               for s in segs), [s.duration for s in segs]
    assert sum(s.duration for s in segs) >= 28.0     # nothing substantial lost
    # first boundary near the 12 s pause (the quietest point in the window)
    assert abs(segs[0].end_s - 12.2) < 1.0


def test_short_neighbours_join_across_small_gaps():
    # 3 s + 0.8 s gap + 3 s -> joined into one ~7 s segment
    x = speech_with_pauses([("v", 3), ("s", 0.8), ("v", 3)])
    dbfs, _, frame_dur = frame_levels(x, SR, CFG)
    regions = speech_regions(dbfs, frame_dur, CFG)
    segs = plan_segments(regions, dbfs, frame_dur, x.size / SR, CFG)
    assert len(segs) == 1
    assert 6.0 <= segs[0].duration <= 8.0


def test_padding_and_bounds():
    x = speech_with_pauses([("s", 1), ("v", 6), ("s", 1)])
    dbfs, _, frame_dur = frame_levels(x, SR, CFG)
    regions = speech_regions(dbfs, frame_dur, CFG)
    segs = plan_segments(regions, dbfs, frame_dur, x.size / SR, CFG)
    assert len(segs) == 1
    seg = segs[0]
    assert seg.start_s >= 0.0 and seg.end_s <= x.size / SR
    assert seg.start_s < 1.0 < seg.end_s               # pad reaches before speech


def test_deterministic():
    x = speech_with_pauses([("v", 25), ("s", 2), ("v", 7)])
    dbfs, _, frame_dur = frame_levels(x, SR, CFG)
    a = plan_segments(speech_regions(dbfs, frame_dur, CFG), dbfs, frame_dur, x.size / SR, CFG)
    b = plan_segments(speech_regions(dbfs, frame_dur, CFG), dbfs, frame_dur, x.size / SR, CFG)
    assert a == b
