"""Tests for the evaluation framework."""
from __future__ import annotations

from pathlib import Path

from foundation.constants import Language
from foundation.shared_utils import generate_sine_wav, write_wav
from voice_engine.datasets import PromptCategory, PromptItem
from voice_engine.evaluation import AUTO_METRICS, HUMAN_METRICS, SynthesisEvaluator
from voice_engine.evaluation.criteria import metric_by_name
from voice_engine.interfaces import SynthesisResult


def _make_result(tmp_path: Path, duration_s: float, chars: int) -> SynthesisResult:
    path = write_wav(tmp_path / "synth.wav", generate_sine_wav(duration_s=duration_s))
    return SynthesisResult(
        audio_path=path,
        sample_rate=24000,
        audio_duration_s=duration_s,
        synthesis_time_s=duration_s * 0.2,
        engine_id="mock",
        request_text_chars=chars,
    )


def _prompt(text: str) -> PromptItem:
    return PromptItem("p1", PromptCategory.PRICING, text, Language.ENGLISH)


def test_evaluator_produces_core_measurements(tmp_path: Path) -> None:
    result = _make_result(tmp_path, duration_s=4.0, chars=60)  # 15 chars/s: normal
    measurements = SynthesisEvaluator().evaluate(result, _prompt("x" * 60))
    names = {m.name for m in measurements}
    assert {"real_time_factor", "synthesis_time_s", "rms_dbfs", "silence_ratio",
            "clipping_ratio", "duration_ratio_vs_expected"} <= names
    assert all(m.source == "auto" for m in measurements)
    assert "speech_rate_anomaly" not in names


def test_evaluator_flags_speech_rate_anomaly(tmp_path: Path) -> None:
    # 600 chars claimed in 2 s of audio -> 300 chars/s: truncated output.
    result = _make_result(tmp_path, duration_s=2.0, chars=600)
    measurements = SynthesisEvaluator().evaluate(result, _prompt("x" * 600))
    names = {m.name for m in measurements}
    assert "speech_rate_anomaly" in names


def test_metric_catalog_separates_sources() -> None:
    assert all(m.source == "auto" for m in AUTO_METRICS)
    assert all(m.source == "human" for m in HUMAN_METRICS)
    auto_names = {m.name for m in AUTO_METRICS}
    human_names = {m.name for m in HUMAN_METRICS}
    assert not auto_names & human_names
    assert metric_by_name("mos_naturalness").source == "human"  # type: ignore[union-attr]
    assert metric_by_name("nope") is None
