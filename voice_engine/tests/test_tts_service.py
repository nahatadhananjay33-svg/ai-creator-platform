"""Tests for the production service layer: config, cache, router."""
from __future__ import annotations

from pathlib import Path

import pytest

from foundation.constants import Language
from foundation.exceptions import AdapterNotAvailableError, ConfigError
from foundation.model_manager import Device
from voice_engine.adapters.mock import MockVoiceAdapter
from voice_engine.interfaces import SynthesisRequest
from voice_engine.tts import (
    EngineRouter,
    SynthesisCacheManager,
    VoiceEngineConfig,
    load_voice_engine_config,
)


# ------------------------------------------------------------------ config
def test_defaults_load_and_bind() -> None:
    config = load_voice_engine_config(apply_env_vars=False)
    assert config.engine.default_model == "kokoro"
    assert "realtime" in config.routing and "quality" in config.routing
    assert config.cache.enabled is True
    assert config.profiles.require_consent is True
    assert config.streaming.chunk_ms == 200


def test_overrides_beat_defaults() -> None:
    config = load_voice_engine_config(
        overrides={"engine": {"default_model": "mock"}, "streaming": {"chunk_ms": 40}},
        apply_env_vars=False,
    )
    assert config.engine.default_model == "mock"
    assert config.streaming.chunk_ms == 40


def test_unknown_keys_rejected() -> None:
    with pytest.raises(ConfigError):
        load_voice_engine_config(
            overrides={"streaming": {"chunk_size": 10}}, apply_env_vars=False
        )
    with pytest.raises(ConfigError):
        VoiceEngineConfig.from_mapping({"routing": {"realtime": "kokoro"}})


# ------------------------------------------------------------------ cache
@pytest.fixture()
def cache(tmp_path: Path) -> SynthesisCacheManager:
    return SynthesisCacheManager(namespace="test_synth", root=tmp_path / "cache")


def _synth(tmp_path: Path, text: str = "Cache me.") -> tuple[SynthesisRequest, MockVoiceAdapter]:
    request = SynthesisRequest(
        text=text, language=Language.ENGLISH, output_path=tmp_path / "a.wav"
    )
    return request, MockVoiceAdapter(device=Device.CPU)


def test_cache_roundtrip(cache: SynthesisCacheManager, tmp_path: Path) -> None:
    request, engine = _synth(tmp_path)
    assert cache.get(request, engine.engine_id) is None
    result = engine.synthesize(request)
    cache.put(request, engine.engine_id, result)
    hit = cache.get(request, engine.engine_id)
    assert hit is not None
    assert hit.metadata["cache_hit"] is True
    assert hit.audio_path == request.output_path
    assert hit.audio_duration_s == pytest.approx(result.audio_duration_s)
    assert hit.synthesis_time_s == 0.0


def test_cache_key_sensitivity(tmp_path: Path) -> None:
    request, engine = _synth(tmp_path)
    base = SynthesisCacheManager.key_for(request, engine.engine_id)
    from dataclasses import replace

    assert SynthesisCacheManager.key_for(replace(request, speed=1.2), "mock") != base
    assert SynthesisCacheManager.key_for(replace(request, emotion="happy"), "mock") != base
    assert SynthesisCacheManager.key_for(request, "kokoro") != base
    # Output path must NOT affect the key (same audio, different destination).
    assert SynthesisCacheManager.key_for(
        replace(request, output_path=tmp_path / "elsewhere.wav"), "mock"
    ) == base


def test_cache_disabled_and_evict(cache: SynthesisCacheManager, tmp_path: Path) -> None:
    request, engine = _synth(tmp_path)
    result = engine.synthesize(request)
    cache.put(request, engine.engine_id, result)
    assert cache.evict(request, engine.engine_id) is True
    assert cache.get(request, engine.engine_id) is None
    disabled = SynthesisCacheManager(
        namespace="test_synth_off", root=tmp_path / "cache2", enabled=False
    )
    disabled.put(request, engine.engine_id, result)
    assert disabled.get(request, engine.engine_id) is None


# ------------------------------------------------------------------ router
def test_router_resolves_first_viable() -> None:
    router = EngineRouter({"realtime": ["f5-tts", "mock"]})
    # f5-tts deps are not installed in the test environment -> mock wins.
    assert router.resolve("realtime") == "mock"


def test_router_constraint_filters() -> None:
    router = EngineRouter({"clone": ["mock"], "bn": ["styletts2"]})
    assert router.resolve("clone", require_cloning=True) == "mock"
    with pytest.raises(AdapterNotAvailableError):
        router.resolve("bn", language=Language.BENGALI)  # styletts2 is EN-only


def test_router_rejects_unknown_configuration() -> None:
    with pytest.raises(ConfigError):
        EngineRouter({"realtime": ["not-a-model"]})
    router = EngineRouter({"realtime": ["mock"]})
    with pytest.raises(ConfigError):
        router.resolve("quality")
