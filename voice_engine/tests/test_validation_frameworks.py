"""Tests for model validation and reference-audio validation (A1.5)."""
from __future__ import annotations

import array
from pathlib import Path

from foundation.constants import Language
from foundation.shared_utils import generate_sine_wav, write_wav
from foundation.shared_utils.audio_io import WavData
from voice_engine.adapters.f5_tts import F5TTSAdapter
from voice_engine.adapters.mock import MockVoiceAdapter
from voice_engine.cloning.reference_validation import (
    ReferenceValidationStudy,
    analyze_clip,
)
from voice_engine.models.validation import ModelValidator


def _speechlike_clip(tmp_path: Path, name: str, seconds: float) -> Path:
    """Tone with silence gaps — enough structure for the analyzer."""
    sr = 24000
    tone = generate_sine_wav(duration_s=2.0, sample_rate=sr)
    gap = array.array("h", [0] * int(0.4 * sr))
    samples = array.array("h")
    while len(samples) < seconds * sr:
        samples.extend(tone.samples)
        samples.extend(gap)
    return write_wav(tmp_path / name, WavData(samples=samples[: int(seconds * sr)], sample_rate=sr))


def test_model_validator_with_mock(tmp_path: Path) -> None:
    ref = _speechlike_clip(tmp_path, "ref.wav", 12)
    validator = ModelValidator(tmp_path / "out")
    result = validator.validate(MockVoiceAdapter(device="cpu"), reference_audio=ref,
                                languages=(Language.ENGLISH, Language.HINDI))
    assert result.valid
    assert result.dependencies_ok and result.loads and result.output_generated
    assert result.reference_accepted is True
    assert result.first_inference_s is not None
    assert result.subsequent_inference_s is not None
    assert set(result.languages_ok) == {"en", "hi"}
    saved = validator.save(result)
    assert saved.exists()


def test_model_validator_reports_missing_dependencies(tmp_path: Path) -> None:
    result = ModelValidator(tmp_path).validate(F5TTSAdapter(device="cpu"))
    if not result.dependencies_ok:  # host interpreter has no f5_tts
        assert not result.valid
        assert "missing" in (result.error or "")


def test_analyze_clip_flags_problems(tmp_path: Path) -> None:
    clean = _speechlike_clip(tmp_path, "clean.wav", 20)
    analysis = analyze_clip(clean)
    assert analysis.duration_s > 19
    assert analysis.speech_duration_s > 10
    assert analysis.clipping_ratio == 0.0

    clipped = write_wav(tmp_path / "clipped.wav",
                        generate_sine_wav(duration_s=10, amplitude=1.0))
    analysis = analyze_clip(clipped)
    assert any("clipping" in w for w in analysis.warnings)


def test_reference_study_recommends_sweet_spot(tmp_path: Path) -> None:
    clips = {d: _speechlike_clip(tmp_path, f"en_{d}.wav", d) for d in (10, 20, 30, 60)}
    study = ReferenceValidationStudy([MockVoiceAdapter(device="cpu")])
    result = study.run(clips)
    rec = result.recommendations["mock"]
    assert rec["recommended_duration_s"] == 20
    assert rec["accepted_durations_s"] == [10, 20, 30, 60]
    # engines without cloning are excluded from the study
    assert all(v.engine_id == "mock" for v in result.verdicts)
