"""Readiness score: band mappings, proxies, weighting, determinism."""
from __future__ import annotations

from production.clean_recording_eval.config import V3Config
from production.clean_recording_eval.score import (format_readiness,
                                                   readiness_score)

CFG = V3Config()


def clip(duration=600.0, speech=480.0, snr=28.0, noise="low", loud=-20.0,
         sr=48000, multi=False, music=False, has_speech=True, silence=0.15):
    return {"duration": duration, "speech_duration": speech, "snr_db": snr,
            "noise_estimate": noise, "loudness_dbfs": loud, "sample_rate": sr,
            "multi_speaker": multi, "has_music": music, "has_speech": has_speech,
            "silence_pct": silence}


def test_excellent_clip_scores_high_everywhere():
    s = readiness_score([clip()], CFG)
    assert s.recording_quality == 100.0     # 28 dB >= 25 dB band top
    assert s.noise_level == 100.0
    assert s.speech_consistency == 100.0    # 0.8 ratio >= 0.70
    assert s.single_speaker == 100.0
    assert s.pronunciation == 100.0         # -20 dBFS inside ideal band
    assert s.microphone == 100.0            # 48 kHz
    assert s.naturalness == 100.0
    assert s.overall == 100.0


def test_poor_clip_scores_low():
    s = readiness_score([clip(snr=8.0, noise="high", speech=120.0, loud=-34.0,
                              sr=16000, multi=True, music=True, silence=0.7)], CFG)
    assert s.recording_quality == 0.0       # below the 10 dB floor
    assert s.noise_level == 15.0
    assert s.speech_consistency == 0.0      # ratio 0.2 below 0.40 floor
    assert s.single_speaker == 25.0
    assert s.pronunciation < 15.0           # near the too-quiet hard limit
    assert s.microphone == 0.0
    assert s.naturalness == 40.0            # -40 music, -20 dead air
    assert s.overall < 20.0


def test_duration_weighted_aggregation():
    long_good = clip(duration=1800.0, speech=1440.0)
    short_bad = clip(duration=10.0, snr=8.0, noise="high", multi=True)
    s = readiness_score([long_good, short_bad], CFG)
    assert s.overall > 95.0                 # the 30-min clip dominates the 10 s one
    assert readiness_score([], CFG).overall == 0.0


def test_deterministic_and_formatted():
    records = [clip(), clip(snr=20.0)]
    a, b = readiness_score(records, CFG), readiness_score(records, CFG)
    assert a == b
    text = format_readiness(a)
    for marker in ("Recording quality (SNR)", "Single-speaker confidence",
                   "Pronunciation consistency (proxy)", "OVERALL READINESS"):
        assert marker in text, marker


def test_weights_sum_to_one():
    total = (CFG.w_recording_quality + CFG.w_noise_level + CFG.w_speech_consistency
             + CFG.w_single_speaker + CFG.w_pronunciation + CFG.w_microphone
             + CFG.w_naturalness)
    assert abs(total - 1.0) < 1e-9
