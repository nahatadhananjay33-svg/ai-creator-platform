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
from avatar_engine.models.diagnostics import AdapterDiagnostic
from avatar_engine.models.interface import GenerationRequest, GenerationResult
from avatar_engine.models.latentsync import LatentSyncAdapter
from avatar_engine.models.liveportrait import LivePortraitAdapter
from avatar_engine.models.mock import MockAvatarAdapter
from avatar_engine.models.musetalk import MuseTalkAdapter
from avatar_engine.models.sadtalker import SadTalkerAdapter
from avatar_engine.research.catalog import production_candidates


class PlannedAvatarAdapter(BaseAvatarAdapter):
    """Placeholder for a researched model whose adapter lands in Phase A4."""

    RUNS_IN_VENV = False  # nothing to probe — there is no adapter yet

    _PLANNED_REASON = (
        "planned model - adapter not implemented yet (Phase A4). "
        "See avatar_engine/research/ and avatar_engine/models/install_specs.py."
    )

    def diagnostics(self, force: bool = False) -> AdapterDiagnostic:
        # Report the true reason (not a misleading 'venv missing'): the model is
        # researched but has no runnable adapter in this codebase.
        if self._diag is None or force:
            self._diag = AdapterDiagnostic(
                model_id=self.engine_id,
                available=False,
                reason=self._PLANNED_REASON,
                runs_in_venv=False,
                python_executable=None,
                venv_dir=None,
                venv_exists=False,
                expected_device=self.device.value,
            )
        return self._diag

    def load(self) -> None:
        raise AdapterNotAvailableError(self._PLANNED_REASON, adapter=self.engine_id)

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
    # Real adapters override their planned placeholders:
    "sadtalker": SadTalkerAdapter,       # A3.5
    "liveportrait": LivePortraitAdapter,  # A3.9
    "musetalk": MuseTalkAdapter,          # A4.0
    "latentsync": LatentSyncAdapter,     # A4.7
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
