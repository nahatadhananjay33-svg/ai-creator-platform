"""Adapter registry and factory.

Phase A3 ships one runnable adapter (mock). Every researched production
candidate is still registered — as a :class:`PlannedAvatarAdapter` that
reports itself unavailable — so benchmark runs enumerate the full candidate
list today and record SKIPPED cases with an honest reason. When a real
adapter lands in Phase A4 it replaces its placeholder here and the whole
benchmark/reporting stack picks it up unchanged.
"""
from __future__ import annotations

from typing import Any, Type

from foundation.exceptions import AdapterNotAvailableError, ModelNotFoundError
from foundation.model_manager import Device

from avatar_engine.models.base import BaseAvatarAdapter
from avatar_engine.models.interface import GenerationRequest, GenerationResult
from avatar_engine.models.liveportrait import LivePortraitAdapter
from avatar_engine.models.mock import MockAvatarAdapter
from avatar_engine.models.sadtalker import SadTalkerAdapter
from avatar_engine.research.catalog import production_candidates


class PlannedAvatarAdapter(BaseAvatarAdapter):
    """Placeholder for a researched model whose adapter lands in Phase A4."""

    def is_available(self) -> bool:
        return False

    def load(self) -> None:
        raise AdapterNotAvailableError(
            f"Adapter '{self.engine_id}' is researched but not yet implemented "
            f"(planned for Phase A4). See avatar_engine/research/ and "
            f"avatar_engine/models/install_specs.py.",
            adapter=self.engine_id,
        )

    def _generate_impl(self, request: GenerationRequest, output_path: Any) -> GenerationResult:
        raise AssertionError("unreachable: load() always raises")  # pragma: no cover


def _planned_adapter_class(model_id: str) -> Type[BaseAvatarAdapter]:
    from avatar_engine.research.catalog import get_profile

    profile = get_profile(model_id)
    return type(
        f"Planned_{model_id.replace('-', '_')}",
        (PlannedAvatarAdapter,),
        {"SPEC": profile.spec},
    )


#: model_id -> adapter class. Real adapters replace planned ones over time.
ADAPTER_CLASSES: dict[str, Type[BaseAvatarAdapter]] = {
    "mock": MockAvatarAdapter,
    **{p.model_id: _planned_adapter_class(p.model_id) for p in production_candidates()},
    # Real adapters (Phase A3.5) override their planned placeholders:
    "sadtalker": SadTalkerAdapter,
    "liveportrait": LivePortraitAdapter,
}


def create_adapter(
    model_id: str,
    device: Device | str = Device.AUTO,
    config: dict[str, Any] | None = None,
) -> BaseAvatarAdapter:
    cls = ADAPTER_CLASSES.get(model_id)
    if cls is None:
        raise ModelNotFoundError(
            f"No avatar adapter registered for {model_id!r}",
            model_id=model_id,
            known=sorted(ADAPTER_CLASSES),
        )
    return cls(device=device, config=config)
