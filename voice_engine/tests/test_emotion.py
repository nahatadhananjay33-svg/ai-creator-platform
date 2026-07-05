"""Tests for the emotion control layer."""
from __future__ import annotations

import pytest

from foundation.constants import Language
from foundation.exceptions import ConfigError
from foundation.model_manager import Device
from voice_engine.adapters.mock import MockVoiceAdapter
from voice_engine.emotion import Emotion, EmotionManager, EmotionSpec, resolve_emotion
from voice_engine.interfaces import SynthesisRequest


@pytest.fixture()
def request_() -> SynthesisRequest:
    return SynthesisRequest(text="Great news!", language=Language.ENGLISH, emotion="excited")


@pytest.fixture()
def engine() -> MockVoiceAdapter:
    return MockVoiceAdapter(device=Device.CPU)


def test_resolve_emotion_accepts_all_forms() -> None:
    assert resolve_emotion(None) is None
    assert resolve_emotion("happy") == EmotionSpec(Emotion.HAPPY)
    assert resolve_emotion(Emotion.SAD).emotion is Emotion.SAD
    spec = EmotionSpec(Emotion.EXCITED, intensity=0.9)
    assert resolve_emotion(spec) is spec
    with pytest.raises(ConfigError):
        resolve_emotion("euphoric")
    with pytest.raises(ConfigError):
        EmotionSpec(Emotion.HAPPY, intensity=1.5)


def test_engine_without_emotion_control_drops_hint(
    request_: SynthesisRequest, engine: MockVoiceAdapter
) -> None:
    # Mock declares emotion_control=False and has no configured strategy.
    manager = EmotionManager()
    out = manager.apply(request_, engine)
    assert out.emotion is None
    assert out.extra == {}
    assert out.text == request_.text


def test_exaggeration_strategy_scales_with_intensity(
    request_: SynthesisRequest, engine: MockVoiceAdapter
) -> None:
    manager = EmotionManager({"mock": "exaggeration"})
    mild = manager.render(request_, engine, EmotionSpec(Emotion.EXCITED, 0.2))
    wild = manager.render(request_, engine, EmotionSpec(Emotion.EXCITED, 1.0))
    assert 0.5 < mild.extra["exaggeration"] < wild.extra["exaggeration"] <= 1.0
    calm = manager.render(request_, engine, EmotionSpec(Emotion.CALM, 1.0))
    assert calm.extra["exaggeration"] < 0.5


def test_instruct_strategy_writes_style_instruction(
    request_: SynthesisRequest, engine: MockVoiceAdapter
) -> None:
    manager = EmotionManager({"mock": "instruct"})
    out = manager.render(request_, engine, EmotionSpec(Emotion.HAPPY, 0.9))
    assert out.extra["instruct"] == "Speak in a very happy tone."
    assert out.emotion == "happy"


def test_neutral_emotion_is_a_no_op(request_: SynthesisRequest, engine: MockVoiceAdapter) -> None:
    manager = EmotionManager({"mock": "exaggeration"})
    out = manager.render(request_, engine, EmotionSpec(Emotion.NEUTRAL))
    assert out is request_


def test_unknown_strategy_rejected() -> None:
    with pytest.raises(ConfigError):
        EmotionManager({"mock": "telepathy"})


def test_default_strategies_cover_a15_engines() -> None:
    manager = EmotionManager()
    assert manager.strategies["chatterbox"] == "exaggeration"
    assert manager.strategies["cosyvoice2"] == "instruct"
