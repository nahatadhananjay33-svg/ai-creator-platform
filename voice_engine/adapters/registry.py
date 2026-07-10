"""Adapter registry: single place that knows every concrete adapter.

Note: Seed-TTS (ByteDance) has no adapter — it is a paper/commercial API
without open weights and is documented in research only
(voice_engine/research/medium_priority_models.md).
"""
from __future__ import annotations

import json
from typing import Any, Type

from foundation.exceptions import ModelNotFoundError
from foundation.model_manager import Device
from foundation.shared_utils.hashing import short_hash
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


# ---------------------------------------------------------------------------
# Process-global adapter reuse (Phase C17 — performance).
#
# ``create_adapter`` always builds a *fresh* adapter (and its next ``load()``
# re-reads the model weights). A single :class:`VoiceEngine` already reuses its
# adapters across calls via its own ``_engines`` cache, but that cache dies with
# the instance — so constructing a new ``VoiceEngine`` (e.g. a second reel in the
# same process, or a forced re-render) would reload the same multi-hundred-MB
# weights from scratch. This tiny process-global cache keeps loaded adapters
# alive across instances, keyed by everything that determines the adapter's
# identity (id + device + config), so "reuse loaded models whenever possible"
# holds beyond a single engine. Output is unaffected: the same weights produce
# the same audio; only the redundant reload is avoided.
# ---------------------------------------------------------------------------
_ADAPTER_CACHE: dict[str, BaseVoiceAdapter] = {}


def _adapter_cache_key(adapter_id: str, device: Device | str, config: dict | None) -> str:
    dev = device.value if isinstance(device, Device) else str(device)
    payload = json.dumps({"id": adapter_id, "device": dev, "config": config or {}},
                         sort_keys=True, default=str)
    return short_hash(payload, 24)


def get_or_create_adapter(
    adapter_id: str,
    device: Device | str = Device.AUTO,
    config: dict[str, Any] | None = None,
    *,
    reuse: bool = True,
) -> BaseVoiceAdapter:
    """Return a cached adapter (reusing its loaded weights) or create + cache one.

    Reuse is keyed by ``(adapter_id, device, config)`` so differently-configured
    engines never share an adapter. Pass ``reuse=False`` for a guaranteed-fresh
    instance (used by isolated tools/tests)."""
    if not reuse:
        return create_adapter(adapter_id, device, config)
    key = _adapter_cache_key(adapter_id, device, config)
    adapter = _ADAPTER_CACHE.get(key)
    if adapter is None:
        adapter = create_adapter(adapter_id, device, config)
        _ADAPTER_CACHE[key] = adapter
    return adapter


def forget_cached_adapter(adapter: BaseVoiceAdapter) -> None:
    """Drop ``adapter`` from the process-global cache (called on unload)."""
    for key in [k for k, v in _ADAPTER_CACHE.items() if v is adapter]:
        _ADAPTER_CACHE.pop(key, None)


def clear_adapter_cache() -> None:
    """Empty the process-global adapter cache (test hygiene / free memory)."""
    _ADAPTER_CACHE.clear()


def cached_adapter_count() -> int:
    """How many adapters are currently held in the process-global cache."""
    return len(_ADAPTER_CACHE)


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
