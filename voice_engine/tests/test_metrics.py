"""Tests for voice_engine.metrics."""
from __future__ import annotations

import array
from pathlib import Path

import pytest

from foundation.shared_utils.audio_io import WavData, generate_sine_wav
from voice_engine.interfaces import SynthesisResult
from voice_engine.metrics import (
    SpeakerSimilarityMetric,
    code_switch_segments,
    compute_audio_stats,
    compute_performance,
    script_coverage,
)
from voice_engine.metrics.performance import aggregate_rtf


def test_audio_stats_on_pure_tone() -> None:
    stats = compute_audio_stats(generate_sine_wav(duration_s=1.0, amplitude=0.4))
    assert stats.duration_s == pytest.approx(1.0, abs=0.01)
    assert stats.clipping_ratio == 0.0
    assert stats.silence_ratio < 0.05
    assert -12.0 < stats.rms_dbfs < -6.0


def test_audio_stats_detects_silence_padding() -> None:
    sr = 16_000
    tone = generate_sine_wav(duration_s=1.0, sample_rate=sr)
    silence = array.array("h", [0] * sr)  # 1 s
    samples = array.array("h")
    samples.extend(silence)
    samples.extend(tone.samples)
    samples.extend(silence)
    stats = compute_audio_stats(WavData(samples=samples, sample_rate=sr))
    assert stats.leading_silence_s == pytest.approx(1.0, abs=0.1)
    assert stats.trailing_silence_s == pytest.approx(1.0, abs=0.1)
    assert stats.silence_ratio == pytest.approx(2 / 3, abs=0.05)


def test_audio_stats_detects_clipping() -> None:
    clipped = generate_sine_wav(duration_s=0.5, amplitude=1.0)
    stats = compute_audio_stats(clipped)
    assert stats.clipping_ratio > 0.0
    assert stats.peak_dbfs == pytest.approx(0.0, abs=0.1)


def test_performance_rtf(tmp_path: Path) -> None:
    result = SynthesisResult(
        audio_path=tmp_path / "x.wav",
        sample_rate=24000,
        audio_duration_s=10.0,
        synthesis_time_s=2.5,
        request_text_chars=150,
    )
    perf = compute_performance(result)
    assert perf.real_time_factor == pytest.approx(0.25)
    assert perf.chars_per_second_audio == pytest.approx(15.0)


def test_aggregate_rtf() -> None:
    agg = aggregate_rtf([0.2, 0.3, 0.25, 0.9])
    assert agg["rtf_median"] == pytest.approx(0.275)
    assert agg["rtf_p95"] == pytest.approx(0.9)


def test_script_coverage_and_code_switching() -> None:
    hinglish = "Booking amount sirf ₹51,000 hai सर, बाकी हम handle कर लेंगे."
    coverage = script_coverage(hinglish)
    assert set(coverage) == {"Latin", "Devanagari"}
    assert sum(coverage.values()) == pytest.approx(1.0, abs=0.01)
    assert code_switch_segments(hinglish) >= 3
    assert code_switch_segments("pure english text") == 1


def test_similarity_metric_unavailable_without_backend() -> None:
    metric = SpeakerSimilarityMetric()
    if not metric.available:
        from foundation.exceptions import MetricUnavailableError

        with pytest.raises(MetricUnavailableError):
            metric._ensure_encoder()
