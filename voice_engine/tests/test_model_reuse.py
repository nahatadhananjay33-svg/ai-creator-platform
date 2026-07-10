"""Process-global adapter reuse tests (Phase C17).

Verifies the model-reuse optimization: a loaded adapter is reused across
``VoiceEngine`` instances (no redundant reload), keyed by id+device+config, and
``unload`` truly forgets it. Hermetic — uses the dependency-free ``mock`` adapter,
no GPU, no weights.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from voice_engine import VoiceEngine
from voice_engine.adapters import (
    cached_adapter_count,
    clear_adapter_cache,
    get_or_create_adapter,
)


def _engine(tmp_path: Path) -> VoiceEngine:
    return VoiceEngine(overrides={
        "engine": {"default_model": "mock"},
        "profiles": {"directory": str(tmp_path / "p")},
        "cache": {"enabled": False},
    })


def test_same_adapter_reused_across_engine_instances(tmp_path):
    a = _engine(tmp_path / "a").load_model("mock")
    b = _engine(tmp_path / "b").load_model("mock")
    assert a is b                       # the SAME adapter object, not a reload
    assert cached_adapter_count() == 1


def test_loaded_weights_are_not_reloaded(tmp_path):
    adapter = _engine(tmp_path / "a").load_model("mock")
    adapter.load()                      # simulate first-use weight load
    assert adapter._loaded is True
    reused = _engine(tmp_path / "b").load_model("mock")
    assert reused is adapter and reused._loaded is True   # no reload happened


def test_get_or_create_caches_and_reuse_flag():
    clear_adapter_cache()
    first = get_or_create_adapter("mock")
    second = get_or_create_adapter("mock")
    assert first is second
    fresh = get_or_create_adapter("mock", reuse=False)
    assert fresh is not first           # reuse=False always builds a new one


def test_different_config_not_shared():
    clear_adapter_cache()
    a = get_or_create_adapter("mock", config={"seed": 1})
    b = get_or_create_adapter("mock", config={"seed": 2})
    assert a is not b
    assert cached_adapter_count() == 2


def test_unload_forgets_cached_adapter(tmp_path):
    eng = _engine(tmp_path / "a")
    eng.load_model("mock")
    assert cached_adapter_count() == 1
    eng.unload_model("mock")
    assert cached_adapter_count() == 0          # global cache cleared too
    assert eng.loaded_models() == []            # instance view unchanged behaviour


def test_reused_adapter_produces_identical_audio(tmp_path):
    e1 = _engine(tmp_path / "a")
    r1 = e1.generate("Reuse me.", output_path=tmp_path / "a.wav", use_cache=False)
    e2 = _engine(tmp_path / "b")        # fresh engine reuses the cached adapter
    r2 = e2.generate("Reuse me.", output_path=tmp_path / "b.wav", use_cache=False)
    assert r1.audio_path.read_bytes() == r2.audio_path.read_bytes()   # identical output
