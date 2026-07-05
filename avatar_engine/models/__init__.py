"""Avatar model layer: generation interface, adapters, and install specs."""

from avatar_engine.models.base import BaseAvatarAdapter
from avatar_engine.models.catalog import (
    all_model_specs,
    benchmarkable_model_ids,
    commercial_ready_specs,
)
from avatar_engine.models.interface import (
    AvatarGenerator,
    GenerationRequest,
    GenerationResult,
)
from avatar_engine.models.mock import MockAvatarAdapter
from avatar_engine.models.registry import ADAPTER_CLASSES, create_adapter

__all__ = [
    "ADAPTER_CLASSES",
    "AvatarGenerator",
    "BaseAvatarAdapter",
    "GenerationRequest",
    "GenerationResult",
    "MockAvatarAdapter",
    "all_model_specs",
    "benchmarkable_model_ids",
    "commercial_ready_specs",
    "create_adapter",
]
