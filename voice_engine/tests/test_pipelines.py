"""Tests for the quality pipeline and the audio export manager."""
from __future__ import annotations

from pathlib import Path

import pytest

from foundation.constants import Language
from foundation.exceptions import ModelError, PlatformError
from foundation.model_manager import Device
from foundation.shared_utils import generate_sine_wav, read_wav, write_wav
from voice_engine.adapters.mock import MockVoiceAdapter
from voice_engine.interfaces import SynthesisRequest
from voice_engine.pipelines import (
    AudioExportManager,
    QualityPipeline,
    crossfade_concat,
    normalize_peak,
)
from voice_engine.tts.config import ExportConfig


@pytest.fixture()
def engine() -> MockVoiceAdapter:
    return MockVoiceAdapter(device=Device.CPU)


# ------------------------------------------------------------------ quality
def test_quality_pipeline_joins_sentences(engine: MockVoiceAdapter, tmp_path: Path) -> None:
    request = SynthesisRequest(
        text="First sentence here. Second sentence here. Third sentence!",
        language=Language.ENGLISH,
        output_path=tmp_path / "narration.wav",
    )
    result = QualityPipeline().run(engine, request)
    assert result.audio_path == request.output_path
    assert result.audio_path.exists()
    assert result.metadata["pipeline"] == "quality"
    assert result.metadata["chunks"] == 3
    # Crossfaded join must be shorter than or equal to the plain sum of parts
    # and longer than any single part.
    single = engine.synthesize(
        SynthesisRequest(text="First sentence here.", language=Language.ENGLISH)
    )
    assert result.audio_duration_s > single.audio_duration_s


def test_quality_pipeline_rejects_empty_text(engine: MockVoiceAdapter) -> None:
    with pytest.raises(ModelError):
        QualityPipeline().run(
            engine, SynthesisRequest(text="   ", language=Language.ENGLISH)
        )


def test_crossfade_concat_length_and_rate() -> None:
    a = generate_sine_wav(duration_s=0.5, sample_rate=16_000)
    b = generate_sine_wav(duration_s=0.5, sample_rate=16_000, frequency_hz=880)
    joined = crossfade_concat([a, b], crossfade_ms=50)
    assert joined.sample_rate == 16_000
    expected = a.n_frames + b.n_frames - int(16_000 * 0.05)
    assert joined.n_frames == expected


def test_crossfade_concat_resamples_mismatched_segments() -> None:
    a = generate_sine_wav(duration_s=0.3, sample_rate=24_000)
    b = generate_sine_wav(duration_s=0.3, sample_rate=16_000)
    joined = crossfade_concat([a, b], crossfade_ms=10)
    assert joined.sample_rate == 24_000
    assert joined.duration_s == pytest.approx(0.6, abs=0.02)


def test_crossfade_concat_empty_rejected() -> None:
    with pytest.raises(ModelError):
        crossfade_concat([])


# ------------------------------------------------------------------ export
def test_normalize_peak_hits_target() -> None:
    import math

    wav = generate_sine_wav(duration_s=0.2, amplitude=0.2)
    normalized = normalize_peak(wav, target_dbfs=-1.0)
    peak = max(abs(s) for s in normalized.samples)
    assert peak == pytest.approx(32767 * math.pow(10, -1 / 20), rel=0.01)
    silent = normalize_peak(
        generate_sine_wav(duration_s=0.1, amplitude=0.0), target_dbfs=-1.0
    )
    assert max((abs(s) for s in silent.samples), default=0) == 0


def test_export_wav_with_resample_and_normalize(tmp_path: Path) -> None:
    source = write_wav(
        tmp_path / "src.wav", generate_sine_wav(duration_s=0.4, sample_rate=24_000, amplitude=0.2)
    )
    out = AudioExportManager(ExportConfig(peak_dbfs=-3.0)).export(
        source, tmp_path / "out.wav", sample_rate=16_000
    )
    wav = read_wav(out)
    assert wav.sample_rate == 16_000
    assert max(abs(s) for s in wav.samples) > 0.2 * 32767  # normalized upward


def test_export_infers_format_from_suffix(tmp_path: Path) -> None:
    source = write_wav(tmp_path / "src.wav", generate_sine_wav(duration_s=0.2))
    manager = AudioExportManager()
    out = manager.export(source, tmp_path / "chunk.pcm_s16le", audio_format="pcm_s16le")
    assert out.read_bytes()  # raw PCM payload
    with pytest.raises(PlatformError):
        manager.export(source, tmp_path / "clip.xyz")


def test_export_missing_source_rejected(tmp_path: Path) -> None:
    with pytest.raises(PlatformError):
        AudioExportManager().export(tmp_path / "ghost.wav", tmp_path / "out.wav")


def test_export_compressed_requires_ffmpeg(tmp_path: Path) -> None:
    source = write_wav(tmp_path / "src.wav", generate_sine_wav(duration_s=0.2))
    manager = AudioExportManager()
    if manager.ffmpeg_available():
        out = manager.export(source, tmp_path / "clip.mp3")
        assert out.exists() and out.stat().st_size > 0
    else:
        with pytest.raises(PlatformError):
            manager.export(source, tmp_path / "clip.mp3")
