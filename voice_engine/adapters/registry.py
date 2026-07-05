"""Adapter registry: single place that knows every concrete adapter.

Note: Seed-TTS (ByteDance) has no adapter — it is a paper/commercial API
without open weights and is documented in research only
(voice_engine/research/medium_priority_models.md).
"""
from __future__ import annotations

from typing import Any, Type

from foundation.exceptions import ModelNotFoundError
from foundation.model_manager import Device
from foundation.model_manager.registry import GLOBAL_MODEL_REGISTRY
from voice_engine.adapters.base import BaseVoiceAdapter
from voice_engine.adapters.chatterbox import ChatterboxAdapter
from voice_engine.adapters.cosyvoice2 import CosyVoice2Adapter
from voice_engine.adapters.dia import DiaAdapter
from voice_engine.adapters.f5_tts import F5TTSAdapter
from voice_engine.adapters.indic_parler import IndicParlerAdapter
from voice_engine.adapters.kokoro import KokoroAdapter
from voice_engine.adapters.melotts import MeloTTSAdapter
from voice_engine.adapters.mock import MockVoiceAdapter
from voice_engine.adapters.openvoice_v2 import OpenVoiceV2Adapter
from voice_engine.adapters.spark_tts import SparkTTSAdapter
from voice_engine.adapters.styletts2 import StyleTTS2Adapter
from voice_engine.adapters.xtts_v2 import XTTSv2Adapter

ADAPTER_CLASSES: dict[str, Type[BaseVoiceAdapter]] = {
    cls.SPEC.model_id: cls
    for cls in (
        MockVoiceAdapter,
        F5TTSAdapter,
        XTTSv2Adapter,
        OpenVoiceV2Adapter,
        ChatterboxAdapter,
        DiaAdapter,
        CosyVoice2Adapter,
        MeloTTSAdapter,
        SparkTTSAdapter,
        StyleTTS2Adapter,
        IndicParlerAdapter,
        KokoroAdapter,
    )
}


def create_adapter(
    adapter_id: str,
    device: Device | str = Device.AUTO,
    config: dict[str, Any] | None = None,
) -> BaseVoiceAdapter:
    """Instantiate an adapter by id (does not load weights)."""
    try:
        cls = ADAPTER_CLASSES[adapter_id]
    except KeyError:
        raise ModelNotFoundError(
            f"Unknown voice adapter: {adapter_id!r}",
            adapter_id=adapter_id,
            known=sorted(ADAPTER_CLASSES),
        ) from None
    return cls(device=device, config=config)


def available_adapter_ids(include_mock: bool = False) -> list[str]:
    """Adapter ids whose optional dependencies are installed on this machine."""
    ids = []
    for adapter_id, cls in ADAPTER_CLASSES.items():
        if adapter_id == "mock" and not include_mock:
            continue
        if cls(device=Device.CPU).is_available():
            ids.append(adapter_id)
    return sorted(ids)


def register_all_specs() -> None:
    """Publish every adapter's ModelSpec into the global model registry."""
    for cls in ADAPTER_CLASSES.values():
        if cls.SPEC.model_id not in GLOBAL_MODEL_REGISTRY:
            GLOBAL_MODEL_REGISTRY.register(cls.SPEC)
