"""Tests for the adapter framework and mock adapter."""
from __future__ import annotations

from pathlib import Path

import pytest

from foundation.constants import Language
from foundation.exceptions import AdapterDependencyError, ModelError, ModelNotFoundError
from foundation.model_manager import Device
from foundation.shared_utils import generate_sine_wav, write_wav
from voice_engine.adapters import ADAPTER_CLASSES, create_adapter, register_all_specs
from voice_engine.adapters.mock import MockVoiceAdapter
from voice_engine.interfaces import StreamingTTSEngine, SynthesisRequest


@pytest.fixture()
def reference_wav(tmp_path: Path) -> Path:
    return write_wav(tmp_path / "ref.wav", generate_sine_wav(duration_s=8.0))


def test_every_adapter_declares_spec_and_capabilities() -> None:
    for adapter_id, cls in ADAPTER_CLASSES.items():
        assert cls.SPEC.model_id == adapter_id
        assert cls.SPEC.license.weights_license, adapter_id
        assert cls.CAPABILITIES.languages, adapter_id
        # Cloning engines must declare a minimum reference duration.
        if cls.CAPABILITIES.zero_shot_cloning:
            assert cls.CAPABILITIES.min_reference_audio_s is not None, adapter_id


def test_register_all_specs_idempotent() -> None:
    register_all_specs()
    register_all_specs()  # must not raise on duplicate


def test_create_adapter_unknown_id() -> None:
    with pytest.raises(ModelNotFoundError):
        create_adapter("does-not-exist")


def test_mock_synthesis(tmp_path: Path) -> None:
    adapter = MockVoiceAdapter(device=Device.CPU)
    request = SynthesisRequest(
        text="Namaste, welcome to Capital Greens.",
        language=Language.HINGLISH,
        output_path=tmp_path / "out.wav",
    )
    result = adapter.synthesize(request)
    assert result.audio_path.exists()
    assert result.audio_duration_s > 0
    assert result.real_time_factor is not None
    assert result.engine_id == "mock"


def test_mock_streaming_yields_final_chunk() -> None:
    adapter = MockVoiceAdapter(device=Device.CPU)
    assert isinstance(adapter, StreamingTTSEngine)
    chunks = list(
        adapter.stream_synthesize(
            SynthesisRequest(text="Short line.", language=Language.ENGLISH)
        )
    )
    assert chunks
    assert chunks[-1].is_final
    assert all(c.sample_rate == chunks[0].sample_rate for c in chunks)


def test_unsupported_language_rejected(tmp_path: Path) -> None:
    adapter = create_adapter("styletts2", device=Device.CPU)  # English-only
    with pytest.raises((ModelError, AdapterDependencyError)):
        adapter.synthesize(
            SynthesisRequest(text="বাংলা", language=Language.BENGALI, output_path=tmp_path / "x.wav")
        )


def test_heavy_adapter_skips_cleanly_without_deps() -> None:
    adapter = create_adapter("f5-tts", device=Device.CPU)
    assert adapter.is_available() is False
    with pytest.raises(AdapterDependencyError) as excinfo:
        adapter.load()
    assert "pip install" in str(excinfo.value)


def test_voice_profile_creation_and_validation(reference_wav: Path) -> None:
    adapter = MockVoiceAdapter(device=Device.CPU)
    profile = adapter.create_voice_profile(reference_wav, display_name="Test Voice")
    assert profile.engine_id == "mock"
    assert profile.reference_audio == reference_wav

    problems = adapter.validate_reference(reference_wav)
    assert problems == []


def test_reference_validation_rejects_short_audio(tmp_path: Path) -> None:
    short = write_wav(tmp_path / "short.wav", generate_sine_wav(duration_s=0.3))
    adapter = MockVoiceAdapter(device=Device.CPU)
    problems = adapter.validate_reference(short)
    assert any("too short" in p for p in problems)


def test_commercial_flags_match_research() -> None:
    # Guard rail: these licensing conclusions drive the platform decision.
    assert ADAPTER_CLASSES["xtts-v2"].SPEC.license.commercial_use is False
    assert ADAPTER_CLASSES["f5-tts"].SPEC.license.commercial_use is False
    assert ADAPTER_CLASSES["chatterbox"].SPEC.license.commercial_use is True
    assert ADAPTER_CLASSES["indic-parler"].SPEC.license.commercial_use is True
    assert ADAPTER_CLASSES["cosyvoice2"].SPEC.license.commercial_use is True
