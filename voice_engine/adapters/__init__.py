"""Model adapters: one thin, uniform wrapper per voice model.

Adapters are production components (Phase A2 serves through them); the
benchmark merely exercises them. Heavy model dependencies are imported only
inside ``load()`` so the platform installs and tests without any of them.
"""

from voice_engine.adapters.base import BaseVoiceAdapter
from voice_engine.adapters.registry import (
    ADAPTER_CLASSES,
    available_adapter_ids,
    cached_adapter_count,
    clear_adapter_cache,
    create_adapter,
    forget_cached_adapter,
    get_or_create_adapter,
    register_all_specs,
)

__all__ = [
    "BaseVoiceAdapter",
    "ADAPTER_CLASSES",
    "available_adapter_ids",
    "create_adapter",
    "get_or_create_adapter",
    "forget_cached_adapter",
    "clear_adapter_cache",
    "cached_adapter_count",
    "register_all_specs",
]
