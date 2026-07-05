"""Regression tests for Phase A3.8.5 audio pipeline validation.

Covers the classifier (real speech / placeholder tone / silent / corrupted /
missing / empty) and the benchmark gate that refuses to drive a real avatar
model with invalid audio. Deterministic and dependency-free (synthetic audio;
no real Kokoro WAVs needed, since those are git-ignored).
"""
from __future__ import annotations

import array
import math

import pytest

from foundation.exceptions import BenchmarkError
from foundation.shared_utils.audio_io import WavData, generate_sine_wav, write_wav
from avatar_engine.benchmark import AvatarBenchmark, AvatarBenchmarkConfig
from voice_engine.metrics import (
    AudioClass,
    validate_kokoro_output,
    validate_wav,
    write_audio_validation_report,
)

_SR = 24_000


# --------------------------------------------------------------- fixtures
def _speechlike(dur: float = 3.0) -> WavData:
    """Amplitude-modulated multi-tone with pauses -> reads as speech."""
    s = array.array("h")
    n = int(dur * _SR)
    t = 0
    while t < n:
        for i in range(int(0.15 * _SR)):
            if t >= n:
                break
            v = (0.3 * math.sin(2 * math.pi * 300 * i / _SR)
                 + 0.2 * math.sin(2 * math.pi * 700 * i / _SR)
                 + 0.15 * math.sin(2 * math.pi * 1300 * i / _SR))
            s.append(int(9000 * v))
            t += 1
        for _ in range(int(0.08 * _SR)):  # syllable gap
            if t >= n:
                break
            s.append(0)
            t += 1
    return WavData(s, _SR, 1)


def _write(path, wav):
    write_wav(path, wav)
    return path


# --------------------------------------------------------------- classifier
def test_real_speech_is_speech(tmp_path):
    v = validate_wav(_write(tmp_path / "s.wav", _speechlike()))
    assert v.audio_class == AudioClass.SPEECH.value
    assert v.is_speech and v.valid and not v.is_placeholder


def test_placeholder_tone_detected(tmp_path):
    v = validate_wav(_write(tmp_path / "t.wav", generate_sine_wav(6.0, 220.0)))
    assert v.audio_class == AudioClass.TONE.value
    assert v.is_placeholder and not v.valid
    assert abs((v.dominant_hz or 0) - 220) <= 40  # coarse grid
    assert "220" in v.reason or "placeholder" in v.reason


def test_other_tone_detected(tmp_path):
    v = validate_wav(_write(tmp_path / "t.wav", generate_sine_wav(4.0, 440.0)))
    assert v.audio_class == AudioClass.TONE.value and v.is_placeholder


def test_silent_audio_detected(tmp_path):
    v = validate_wav(_write(tmp_path / "z.wav", WavData(array.array("h", [0] * _SR * 2), _SR, 1)))
    assert v.audio_class == AudioClass.SILENT.value and not v.valid


def test_corrupted_wav_detected(tmp_path):
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"RIFFnope not a real wav file at all")
    v = validate_wav(bad)
    assert v.audio_class == AudioClass.CORRUPTED.value and not v.valid


def test_missing_wav_detected(tmp_path):
    v = validate_wav(tmp_path / "nope.wav")
    assert v.audio_class == AudioClass.MISSING.value and not v.exists and not v.valid


def test_empty_wav_detected(tmp_path):
    v = validate_wav(_write(tmp_path / "e.wav", WavData(array.array("h"), _SR, 1)))
    assert v.audio_class == AudioClass.EMPTY.value and not v.valid


def test_report_fields_populated(tmp_path):
    v = validate_wav(_write(tmp_path / "s.wav", _speechlike()))
    for field in ("duration_s", "sample_rate", "rms_dbfs", "peak_dbfs", "silence_ratio",
                  "dominant_hz", "spectral_flatness", "tonal_energy_ratio", "envelope_cv",
                  "file_size_bytes", "crest_factor", "zero_crossing_rate"):
        assert getattr(v, field) is not None, field


def test_kokoro_output_duration_mismatch_flagged(tmp_path):
    v = validate_kokoro_output(_write(tmp_path / "s.wav", _speechlike(dur=3.0)),
                               expected_duration_s=30.0)
    assert v.is_speech and v.duration_ok is False
    assert "duration" in v.reason


def test_write_report_creates_files(tmp_path):
    vs = [validate_wav(_write(tmp_path / "s.wav", _speechlike())),
          validate_wav(_write(tmp_path / "t.wav", generate_sine_wav(4.0, 220.0)))]
    reports = write_audio_validation_report(vs, tmp_path / "rep", label_by_path={vs[0].path: "hello"})
    assert reports["json"].exists() and reports["markdown"].exists()
    import json
    payload = json.loads(reports["json"].read_text(encoding="utf-8"))
    assert payload["summary"]["speech"] == 1 and payload["summary"]["placeholder"] == 1
    assert "Audio Validation Report" in reports["markdown"].read_text(encoding="utf-8")


# --------------------------------------------------------------- benchmark gate
_SCENARIOS = ("neutral-intro-en", "neutral-pricing-en")  # first two in the dataset


def _assets_with(tmp_path, audio_for):
    """Create an assets dir; audio_for maps scenario_id -> WavData."""
    adir = tmp_path / "assets"
    adir.mkdir()
    for sid, wav in audio_for.items():
        write_wav(adir / f"{sid}.wav", wav)
    return adir


def _config(tmp_path, adir, adapters, **kw):
    return AvatarBenchmarkConfig(
        adapters=adapters, assets_dir=str(adir), max_scenarios=2,
        output_dir=str(tmp_path / "runs"), allow_placeholder_assets=True,
        monitor_resources=False, **kw,
    )


def test_gate_all_tone_real_adapter_raises(tmp_path):
    adir = _assets_with(tmp_path, {s: generate_sine_wav(4.0, 220.0) for s in _SCENARIOS})
    cfg = _config(tmp_path, adir, ["sadtalker"], validate_audio=True)
    with pytest.raises(BenchmarkError):
        AvatarBenchmark(cfg).run()  # stops before any avatar generation


def test_gate_skips_tone_but_keeps_speech(tmp_path):
    adir = _assets_with(tmp_path, {
        "neutral-intro-en": _speechlike(),
        "neutral-pricing-en": generate_sine_wav(4.0, 220.0),
    })
    cfg = _config(tmp_path, adir, ["sadtalker"], validate_audio=True)
    cases = AvatarBenchmark(cfg).build_cases(tmp_path / "run")
    skip = {c.avatar_scenario.scenario_id: c.skip_reason for c in cases}
    assert skip["neutral-intro-en"] is None                    # real speech -> runs
    assert skip["neutral-pricing-en"] is not None              # tone -> skipped
    assert "audio validation failed" in skip["neutral-pricing-en"]


def test_gate_exempts_mock_adapter(tmp_path):
    adir = _assets_with(tmp_path, {s: generate_sine_wav(4.0, 220.0) for s in _SCENARIOS})
    cfg = _config(tmp_path, adir, ["mock"], validate_audio=True)
    run, reports = AvatarBenchmark(cfg).run()
    assert any(c.status.value == "passed" for c in run.cases)   # mock ran on tone audio
    assert "audio_validation" in reports                        # report still emitted


def test_validate_audio_false_disables_gate(tmp_path):
    adir = _assets_with(tmp_path, {s: generate_sine_wav(4.0, 220.0) for s in _SCENARIOS})
    cfg = _config(tmp_path, adir, ["sadtalker"], validate_audio=False)
    cases = AvatarBenchmark(cfg).build_cases(tmp_path / "run")
    assert all(c.skip_reason is None for c in cases)            # no gate when disabled
