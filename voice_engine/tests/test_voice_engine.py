"""Tests for the VoiceEngine production facade."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from foundation.constants import Language
from foundation.exceptions import ModelError
from foundation.shared_utils import generate_sine_wav, write_wav
from voice_engine import VoiceEngine
from voice_engine.emotion import Emotion, EmotionSpec
from voice_engine.voices import ConsentMissingError


@pytest.fixture()
def engine(tmp_path: Path) -> VoiceEngine:
    return VoiceEngine(
        overrides={
            "engine": {"default_model": "mock"},
            "routing": {"realtime": ["mock"], "quality": ["mock"], "cloning": ["mock"]},
            "profiles": {"directory": str(tmp_path / "profiles")},
            "cache": {"directory": str(tmp_path / "cache"), "namespace": "test_engine"},
        },
    )


@pytest.fixture()
def reference_wav(tmp_path: Path) -> Path:
    return write_wav(tmp_path / "ref.wav", generate_sine_wav(duration_s=8.0))


# ------------------------------------------------------------------ models
def test_load_switch_unload_models(engine: VoiceEngine) -> None:
    assert engine.active_model is None
    adapter = engine.load_model()  # config default
    assert adapter.engine_id == "mock"
    assert engine.active_model == "mock"
    assert engine.loaded_models() == ["mock"]
    engine.switch_model("mock")
    engine.unload_model()
    assert engine.active_model is None
    assert engine.loaded_models() == []


def test_model_routing_by_use_case(engine: VoiceEngine) -> None:
    assert engine.model_for_use_case("realtime") == "mock"
    assert engine.model_for_use_case("quality", language="hi") == "mock"


# ------------------------------------------------------------------ generate
def test_generate_applies_pronunciation_and_writes_audio(
    engine: VoiceEngine, tmp_path: Path
) -> None:
    result = engine.generate(
        "RERA approved!", language="en", output_path=tmp_path / "out.wav", use_cache=False
    )
    assert result.audio_path.exists()
    assert result.engine_id == "mock"
    # Pronunciation rewrite happened before synthesis (request length grew).
    assert result.request_text_chars > len("RERA approved!")


def test_generate_serves_second_call_from_cache(engine: VoiceEngine, tmp_path: Path) -> None:
    first = engine.generate("Cache this line.", output_path=tmp_path / "a.wav")
    assert "cache_hit" not in first.metadata
    second = engine.generate("Cache this line.", output_path=tmp_path / "b.wav")
    assert second.metadata["cache_hit"] is True
    assert second.audio_path == tmp_path / "b.wav"
    assert second.audio_path.exists()


def test_generate_long_form_uses_quality_pipeline(engine: VoiceEngine) -> None:
    result = engine.generate(
        "One sentence. Two sentences. Three sentences!", long_form=True, use_cache=False
    )
    assert result.metadata["pipeline"] == "quality"
    assert result.metadata["chunks"] == 3


def test_generate_rejects_empty_text(engine: VoiceEngine) -> None:
    with pytest.raises(ModelError):
        engine.generate("   ")


def test_agenerate(engine: VoiceEngine) -> None:
    result = asyncio.run(engine.agenerate("Async line.", use_cache=False))
    assert result.audio_path.exists()


def test_generate_with_emotion_spec(engine: VoiceEngine) -> None:
    result = engine.generate(
        "So exciting!",
        emotion=EmotionSpec(Emotion.EXCITED, intensity=0.8),
        use_cache=False,
    )
    assert result.audio_path.exists()


# ------------------------------------------------------------------ streaming
def test_stream_yields_final_chunk(engine: VoiceEngine) -> None:
    chunks = list(engine.stream("Short. Line."))
    assert chunks and chunks[-1].is_final


def test_astream(engine: VoiceEngine) -> None:
    async def collect() -> list:
        return [c async for c in engine.astream("Hello there.")]

    chunks = asyncio.run(collect())
    assert chunks and chunks[-1].is_final


# ------------------------------------------------------------------ cloning/profiles
def test_clone_save_load_roundtrip(engine: VoiceEngine, reference_wav: Path) -> None:
    profile = engine.clone_voice(
        reference_wav, "Agent Priya", language_hint="hi",
        consent="P. Sharma, 2026-07-04, marketing",
    )
    assert profile.engine_id == "mock"
    loaded = engine.load_profile(profile.profile_id)
    assert loaded.display_name == "Agent Priya"
    assert engine.list_profiles(engine_id="mock")
    result = engine.generate("With cloned voice.", voice=profile.profile_id, use_cache=False)
    assert result.audio_path.exists()
    assert engine.delete_profile(profile.profile_id) is True


def test_clone_without_consent_cannot_be_saved(
    engine: VoiceEngine, reference_wav: Path
) -> None:
    with pytest.raises(ConsentMissingError):
        engine.clone_voice(reference_wav, "No Consent Voice")
    profile = engine.clone_voice(reference_wav, "Unsaved Voice", save=False)
    assert not engine.profiles.exists(profile.profile_id)


def test_profile_engine_mismatch_rejected(engine: VoiceEngine, reference_wav: Path) -> None:
    profile = engine.clone_voice(
        reference_wav, "Priya", consent="ok", save=False
    )
    from dataclasses import replace

    foreign = replace(profile, engine_id="kokoro")
    with pytest.raises(ModelError):
        engine.generate("Hi", voice=foreign, use_cache=False)


# ------------------------------------------------------------------ export
def test_export_from_result(engine: VoiceEngine, tmp_path: Path) -> None:
    result = engine.generate("Export me.", use_cache=False)
    out = engine.export(result, tmp_path / "final.wav", sample_rate=16_000)
    from foundation.shared_utils import read_wav

    assert read_wav(out).sample_rate == 16_000


# ------------------------------------------------------------------ lifecycle
def test_context_manager_unloads(tmp_path: Path) -> None:
    with VoiceEngine(
        overrides={
            "engine": {"default_model": "mock"},
            "profiles": {"directory": str(tmp_path / "p")},
            "cache": {"enabled": False},
        }
    ) as voice:
        voice.generate("Inside context.", use_cache=False)
        assert voice.loaded_models() == ["mock"]
    assert voice.loaded_models() == []
