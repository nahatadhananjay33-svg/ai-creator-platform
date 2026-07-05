"""Model adapters: one thin, uniform wrapper per voice model.

Adapters are production components (Phase A2 serves through them); the
benchmark merely exercises them. Heavy model dependencies are imported only
inside ``load()`` so the platform installs and tests without any of them.
"""

from voice_engine.adapters.base import BaseVoiceAdapter
from voice_engine.adapters.registry import (
    ADAPTER_CLASSES,
    available_adapter_ids,
    create_adapter,
    register_all_specs,
)

__all__ = [
    "BaseVoiceAdapter",
    "ADAPTER_CLASSES",
    "available_adapter_ids",
    "create_adapter",
    "register_all_specs",
]
