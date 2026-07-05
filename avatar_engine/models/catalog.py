"""Catalog views over avatar model specs (mirrors voice_engine.models.catalog)."""
from __future__ import annotations

from foundation.model_manager import ModelSpec

from avatar_engine.research.catalog import all_profiles


def all_model_specs(include_mock: bool = False) -> list[ModelSpec]:
    """Every researched model's spec, sorted by model_id."""
    specs = [p.spec for p in all_profiles()]
    if include_mock:
        from avatar_engine.models.mock import MockAvatarAdapter

        specs.append(MockAvatarAdapter.SPEC)
    return sorted(specs, key=lambda s: s.model_id)


def commercial_ready_specs() -> list[ModelSpec]:
    """Models whose weights we may deploy commercially today, as-shipped."""
    return [s for s in all_model_specs() if s.license.commercial_use]


def benchmarkable_model_ids() -> list[str]:
    """Adapter ids the benchmark can enumerate right now (incl. planned)."""
    from avatar_engine.models.registry import ADAPTER_CLASSES

    return sorted(ADAPTER_CLASSES)
