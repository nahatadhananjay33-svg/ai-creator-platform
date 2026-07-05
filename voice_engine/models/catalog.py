"""Catalog views over adapter model specs."""
from __future__ import annotations

from foundation.model_manager import ModelSpec
from voice_engine.adapters.registry import ADAPTER_CLASSES


def all_model_specs(include_mock: bool = False) -> list[ModelSpec]:
    """Every candidate model's spec, sorted by model_id."""
    specs = [
        cls.SPEC
        for cls in ADAPTER_CLASSES.values()
        if include_mock or cls.SPEC.model_id != "mock"
    ]
    return sorted(specs, key=lambda s: s.model_id)


def commercial_ready_specs() -> list[ModelSpec]:
    """Models whose weights we may deploy commercially today."""
    return [s for s in all_model_specs() if s.license.commercial_use]
