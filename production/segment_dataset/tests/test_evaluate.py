"""Segment evaluation: metrics reuse, V4 speaker/noise policies, storage."""
from __future__ import annotations

import numpy as np
import pytest

from production.segment_dataset.config import V4Config
from production.segment_dataset.evaluate import (decide_segment,
                                                 evaluate_segment,
                                                 speaker_confidence,
                                                 write_segment_wav)
from production.segment_dataset.models import Segment, SegmentRecord
from production.segment_dataset.storage import (load_segments, row_to_record,
                                                write_all)
from production.voice_dataset.models import AudioMeta, Detection

from .conftest import SR, quiet, speech_with_pauses, tone, write_wav

CFG = V4Config()


def _meta(speech=8.0, dur=10.0, loud=-20.0, silence=0.2):
    return AudioMeta(duration=dur, sample_rate=SR, channels=1, bitrate=SR * 16,
                     silence_pct=silence, speech_duration=speech, loudness_dbfs=loud)


def _det(snr=25.0, speech=True, music=False, noise="low", floor=-60.0):
    return Detection(has_speech=speech, multi_speaker=False, has_music=music,
                     noise_floor_dbfs=floor, snr_db=snr, noise_estimate=noise)


def test_decide_accepts_clear_speech_and_orders_reasons():
    ok, reason = decide_segment(_meta(), _det(), "excellent", 0.0, CFG)
    assert ok and "clear speech" in reason

    assert decide_segment(_meta(), _det(speech=False), "poor", 0.0, CFG) \
        == (False, "no speech detected")
    ok, reason = decide_segment(_meta(speech=1.5), _det(), "good", 0.0, CFG)
    assert not ok and "segment too short" in reason
    ok, reason = decide_segment(_meta(loud=-2.0), _det(), "good", 0.0, CFG)
    assert not ok and "clipping" in reason
    ok, reason = decide_segment(_meta(loud=-50.0), _det(), "good", 0.0, CFG)
    assert not ok and "too quiet" in reason


def test_speaker_policy_high_confidence_only():
    # ordinary/emotional pitch variation (confidence below 0.8) never rejects
    ok, _ = decide_segment(_meta(), _det(), "good", 0.79, CFG)
    assert ok
    ok, reason = decide_segment(_meta(), _det(), "good", 0.85, CFG)
    assert not ok and "overlapping speaker" in reason


def test_noise_policy_masking_only():
    # steady ambience with clear speech (high SNR, even a 'high' noise label) passes
    ok, _ = decide_segment(_meta(), _det(snr=22.0, noise="high", floor=-38.0),
                           "fair", 0.0, CFG)
    assert ok
    # noise that actually masks speech (low SNR) rejects with the exact reason
    ok, reason = decide_segment(_meta(), _det(snr=12.0), "fair", 0.0, CFG)
    assert not ok and "background noise masks speech" in reason


def test_music_alone_does_not_reject_when_speech_clear():
    ok, _ = decide_segment(_meta(), _det(music=True, snr=24.0), "good", 0.0, CFG)
    assert ok


def test_speaker_confidence_steady_vs_alternating_pitch(tmp_path):
    steady = write_wav(tmp_path / "steady.wav", tone(10, f0=150.0))
    conf_s, iqr_s = speaker_confidence(steady, CFG)
    assert conf_s < 0.2 and iqr_s < 60.0

    # two alternating 'voices' an octave apart -> wide IQR -> high confidence
    two = np.concatenate([tone(1.0, f0=110.0) if i % 2 == 0 else tone(1.0, f0=290.0)
                          for i in range(10)])
    conf_t, iqr_t = speaker_confidence(write_wav(tmp_path / "two.wav", two), CFG)
    assert conf_t >= 0.8 and iqr_t > iqr_s

    assert speaker_confidence(write_wav(tmp_path / "sil.wav", quiet(4)), CFG) == (0.0, 0.0)


def test_evaluate_segment_end_to_end(tmp_path):
    x = speech_with_pauses([("v", 8), ("s", 0.4), ("v", 4)])
    seg = Segment(start_s=0.0, end_s=x.size / SR)
    wav = write_segment_wav(x, SR, seg, tmp_path / "seg.wav")
    # a speech-dense segment needs the SOURCE noise floor for a correct SNR
    rec = evaluate_segment(wav, seg, "source.mp4", "clean_mic", 1, CFG,
                           source_noise_floor=-75.0)

    assert rec.accepted, rec.reason
    assert rec.noise_floor_dbfs == -75.0 and rec.noise_estimate == "low"
    assert rec.source_file == "source.mp4" and rec.source_kind == "clean_mic"
    assert rec.snr_db > 18.0 and rec.sample_rate == SR
    assert 0.0 <= rec.multi_speaker_confidence < 0.8
    assert rec.start_s == 0.0 and rec.duration == pytest.approx(12.4, abs=0.2)


def test_write_segment_wav_slices_correctly(tmp_path):
    x = np.concatenate([quiet(2), tone(3), quiet(2)])
    wav = write_segment_wav(x, SR, Segment(start_s=2.0, end_s=5.0), tmp_path / "s.wav")
    import wave
    with wave.open(str(wav), "rb") as w:
        assert w.getnframes() == 3 * SR and w.getframerate() == SR


def test_storage_roundtrip(tmp_path):
    rec = SegmentRecord(
        id=1, source_file="a.mp4", source_kind="youtube", segment_file="a_0001.wav",
        start_s=1.5, end_s=13.0, duration=11.5, speech_duration=10.2,
        quality="excellent", accepted=True, reason="clear speech",
        snr_db=27.3, loudness_dbfs=-19.2, noise_floor_dbfs=-58.0,
        noise_estimate="low", has_music=False, multi_speaker_confidence=0.12,
        f0_iqr_hz=42.0, sample_rate=48000, audio_path="x/a_0001.wav")
    write_all([rec], tmp_path)
    for f in ("dataset.sqlite", "dataset.csv", "dataset.xlsx"):
        assert (tmp_path / f).exists(), f
    rows = load_segments(tmp_path / "dataset.sqlite")
    assert len(rows) == 1 and rows[0]["accepted"] is True
    assert row_to_record(rows[0]) == rec
