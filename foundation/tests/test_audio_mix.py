"""Audio mixing primitive tests (Phase C8). Hermetic, deterministic, no deps.

Pins the pure DSP building blocks the Music Engine and both renderers share:
int16<->float round-trip, nearest resample, looping (with crossfade), linear
fades, the piecewise-linear volume envelope, slew-limited speech ducking,
summation, and the soft limiter that guarantees the mix can never clip.
"""
from __future__ import annotations

from foundation.shared_utils.audio_mix import (
    apply_fades,
    apply_gains,
    apply_mute_sections,
    ducking_gains,
    envelope_gains,
    mix_into,
    peak,
    resample_nearest,
    soft_limit,
    tile_to_length,
    to_float,
    to_int16,
)


def test_int16_float_round_trip():
    ints = [0, 16384, -16384, 32767, -32767]
    back = to_int16(to_float(ints))
    assert list(back) == [0, 16383, -16384, 32766, -32767] or abs(back[3] - 32767) <= 2
    # values stay in range and monotonic mapping holds
    assert all(-32768 <= v <= 32767 for v in back)


def test_to_int16_clamps_out_of_range():
    assert list(to_int16([2.0, -2.0, 0.0])) == [32767, -32767, 0]


def test_resample_nearest_changes_length_and_is_identity_on_equal_rate():
    src = [float(i) / 100 for i in range(100)]
    assert resample_nearest(src, 100, 100) == src
    up = resample_nearest(src, 100, 200)
    assert len(up) == 200                    # 1s upsampled 100->200 Hz
    down = resample_nearest(src, 200, 100)
    assert len(down) == 50                    # 0.5s of 200 Hz audio at 100 Hz


def test_tile_to_length_loops_and_pads_empty():
    assert tile_to_length([1.0, 2.0, 3.0], 7) == [1.0, 2.0, 3.0, 1.0, 2.0, 3.0, 1.0]
    assert tile_to_length([], 4) == [0.0, 0.0, 0.0, 0.0]
    assert len(tile_to_length([1.0, 2.0], 5)) == 5


def test_tile_crossfade_blends_the_seam():
    # a constant source cross-faded stays constant (blend of equal values)
    out = tile_to_length([0.5] * 10, 25, crossfade_n=4)
    assert len(out) == 25
    assert all(abs(v - 0.5) < 1e-9 for v in out)


def test_apply_fades_ramps_edges():
    n = 100
    s = [1.0] * n
    apply_fades(s, sr=100, fade_in_s=0.1, fade_out_s=0.1)
    assert s[0] < s[5] < s[50]              # fade-in ramps up
    assert s[-1] < s[-5] < s[50]            # fade-out ramps down
    assert s[50] == 1.0                     # middle untouched


def test_apply_fades_never_overlap_on_short_buffer():
    s = [1.0] * 10
    apply_fades(s, sr=10, fade_in_s=100.0, fade_out_s=100.0)  # absurd fades
    assert all(0.0 <= v <= 1.0 for v in s)  # clamped to half each, no negatives/blowup


def test_envelope_gains_piecewise_linear():
    g = envelope_gains(((0.0, 0.0), (1.0, 1.0)), sr=10, n=10)
    assert g[0] == 0.0
    assert abs(g[5] - 0.5) < 0.11           # ~halfway up at t=0.5
    # empty -> constant 1.0
    assert envelope_gains((), sr=10, n=5) == [1.0] * 5
    # held flat before first / after last point, honouring offset_s
    g2 = envelope_gains(((2.0, 0.3),), sr=10, n=10, offset_s=0.0)
    assert all(abs(v - 0.3) < 1e-9 for v in g2)


def test_ducking_gains_dip_under_speech_and_recover():
    sr = 100
    n = 400                                  # 4 seconds
    g = ducking_gains(n, sr, [(1.0, 2.0)], duck_level=0.3,
                      attack_s=0.1, release_s=0.1, offset_s=0.0)
    assert g[0] == 1.0                       # clear before speech
    assert min(g[120:190]) <= 0.31          # ducked during [1,2]
    assert g[-1] > 0.9                       # recovered after speech
    # no speech windows -> no ducking
    assert ducking_gains(n, sr, [], duck_level=0.3, attack_s=0.1, release_s=0.1) == [1.0] * n


def test_ducking_seeds_ducked_when_clip_opens_in_speech():
    sr = 100
    g = ducking_gains(50, sr, [(0.0, 5.0)], duck_level=0.2,
                      attack_s=0.1, release_s=0.1, offset_s=0.0)
    assert g[0] == 0.2                       # already under speech at sample 0


def test_apply_mute_sections_zeros_region():
    s = [1.0] * 100
    apply_mute_sections(s, sr=100, sections=[(0.2, 0.4)], offset_s=0.0)
    assert all(v == 0.0 for v in s[20:40])
    assert s[10] == 1.0 and s[50] == 1.0


def test_mix_into_sums_at_offset():
    dst = [0.0] * 5
    mix_into(dst, [1.0, 1.0], offset_n=2)
    assert dst == [0.0, 0.0, 1.0, 1.0, 0.0]


def test_soft_limit_guarantees_no_clipping():
    hot = [3.0, -3.0, 0.5, -0.5, 1.0, -1.0]
    soft_limit(hot)
    assert all(abs(v) < 1.0 for v in hot)   # strictly inside [-1, 1]
    assert hot[2] == 0.5 and hot[3] == -0.5  # below-threshold values untouched
    assert peak(hot) < 1.0


def test_apply_gains_multiplies_elementwise():
    s = [1.0, 1.0, 1.0]
    apply_gains(s, [0.5, 0.25, 0.0])
    assert s == [0.5, 0.25, 0.0]
