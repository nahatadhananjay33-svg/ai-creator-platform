"""Regression tests for Phase A3.10 — Kokoro English G2P dependency.

Pin the fix for spaCy ``[E050] Can't find model 'en_core_web_sm'``: the kokoro
installer fetches the model, and the audio pipeline verifies/self-heals it
before generating. Deterministic (no spaCy/kokoro install, no network) via
monkeypatching ``importlib.util.find_spec``.
"""
from __future__ import annotations

import importlib.util

import pytest

from voice_engine.adapters import kokoro_g2p
from voice_engine.models.install_specs import INSTALL_SPECS


# --------------------------------------------------------------- installer spec
def test_kokoro_spec_fetches_english_g2p_model():
    pf = INSTALL_SPECS["kokoro"].prefetch_code
    assert pf and "en_core_web_sm" in pf
    # version-matched download + pip bootstrap for uv's pip-less venvs
    assert "download(" in pf and "ensurepip" in pf


def test_model_name_matches_error():
    assert kokoro_g2p.EN_G2P_MODEL == "en_core_web_sm"


# --------------------------------------------------------------- verification helper
def test_is_model_installed_true_for_stdlib():
    assert kokoro_g2p.is_model_installed("json") is True


def test_is_model_installed_false_when_absent():
    assert kokoro_g2p.is_model_installed("en_core_web_sm_definitely_absent") is False


def _fake_find_spec(present: set[str]):
    real = importlib.util.find_spec

    def _spec(name, *a, **k):
        if name in present:
            return object()  # truthy "found"
        if name.startswith(("en_core_web_sm", "spacy", "pip")):
            return None
        return real(name, *a, **k)

    return _spec


def test_ensure_noop_when_model_present(monkeypatch):
    monkeypatch.setattr(importlib.util, "find_spec", _fake_find_spec({"en_core_web_sm"}))
    assert kokoro_g2p.ensure_en_core_web_sm() is True  # already present -> no download


def test_ensure_raises_clearly_when_spacy_missing(monkeypatch):
    # model absent AND spaCy absent -> actionable error, not a bare ImportError.
    monkeypatch.setattr(importlib.util, "find_spec", _fake_find_spec(set()))
    with pytest.raises(RuntimeError) as exc:
        kokoro_g2p.ensure_en_core_web_sm()
    assert "spaCy is not installed" in str(exc.value)
    assert "install_models" in str(exc.value)


def test_generate_scenario_audio_verifies_model_first():
    # The audio pipeline must call the verification helper before synthesizing.
    import inspect

    from avatar_engine.scripts import generate_scenario_audio as gsa

    src = inspect.getsource(gsa.main)
    assert "ensure_en_core_web_sm" in src
