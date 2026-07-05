"""Central model registry.

Engines register their :class:`ModelSpec` objects here at import time so any
part of the platform (benchmark, reporting, serving, docs generation) can
enumerate what exists without importing heavy adapter modules.
"""
from __future__ import annotations

from typing import Iterator

from foundation.exceptions import ModelNotFoundError
from foundation.logging import get_logger
from foundation.model_manager.spec import ModelSpec

logger = get_logger("foundation.model_manager")


class ModelRegistry:
    """Thread-unsafe (import-time) registry of model specs, keyed by model_id."""

    def __init__(self) -> None:
        self._specs: dict[str, ModelSpec] = {}

    def register(self, spec: ModelSpec, replace: bool = False) -> None:
        if spec.model_id in self._specs and not replace:
            raise ValueError(f"Model already registered: {spec.model_id}")
        self._specs[spec.model_id] = spec
        logger.debug("Registered model spec", extra={"context": {"model_id": spec.model_id}})

    def get(self, model_id: str) -> ModelSpec:
        try:
            return self._specs[model_id]
        except KeyError:
            raise ModelNotFoundError(
                f"Model not registered: {model_id!r}",
                model_id=model_id,
                known=sorted(self._specs),
            ) from None

    def __contains__(self, model_id: str) -> bool:
        return model_id in self._specs

    def __iter__(self) -> Iterator[ModelSpec]:
        return iter(self._specs.values())

    def __len__(self) -> int:
        return len(self._specs)

    def by_family(self, family: str) -> list[ModelSpec]:
        return [s for s in self._specs.values() if s.family == family]

    def by_tag(self, tag: str) -> list[ModelSpec]:
        return [s for s in self._specs.values() if tag in s.tags]


#: Global platform registry. Engines call ``GLOBAL_MODEL_REGISTRY.register(...)``.
GLOBAL_MODEL_REGISTRY = ModelRegistry()
