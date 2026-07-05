"""Base adapter implementing the shared avatar generation lifecycle.

Concrete adapters supply:
- ``SPEC``: the :class:`ModelSpec` (read from the research catalog)
- ``REQUIRED_INPUTS``: which request fields the task needs
- ``IMPORT_PACKAGES`` / ``PIP_PACKAGES``: dependency declarations
- ``_load_impl`` / ``_unload_impl`` / ``_generate_impl``: model calls

The base class owns availability checks, lazy loading, input validation,
timing, and output-file management — same division of labor as
``voice_engine.adapters.base.BaseVoiceAdapter``.
"""
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path
from typing import Any, ClassVar

from foundation.exceptions import AdapterDependencyError, ModelError
from foundation.logging import get_logger
from foundation.model_manager import Device, ModelSpec, resolve_device
from foundation.shared_utils import Stopwatch, short_hash

from avatar_engine.models.interface import (
    AvatarGenerator,
    GenerationRequest,
    GenerationResult,
)

logger = get_logger("avatar_engine.models")

#: Request fields an adapter may declare as required.
_KNOWN_INPUTS = ("source_image", "driving_audio", "driving_video")


class BaseAvatarAdapter(AvatarGenerator):
    """Shared lifecycle for all avatar model adapters."""

    SPEC: ClassVar[ModelSpec]
    #: Which GenerationRequest fields must be present and exist on disk.
    REQUIRED_INPUTS: ClassVar[tuple[str, ...]] = ("source_image", "driving_audio")
    #: Import names probed by :meth:`is_available`.
    IMPORT_PACKAGES: ClassVar[tuple[str, ...]] = ()
    #: pip package names shown in install hints.
    PIP_PACKAGES: ClassVar[tuple[str, ...]] = ()

    def __init__(self, device: Device | str = Device.AUTO, config: dict[str, Any] | None = None) -> None:
        self.device = resolve_device(device)
        self.config: dict[str, Any] = config or {}
        self._loaded = False
        self._model: Any = None

    # ------------------------------------------------------------------ AvatarGenerator
    @property
    def engine_id(self) -> str:
        return self.SPEC.model_id

    @property
    def spec(self) -> ModelSpec:
        return self.SPEC

    def is_available(self) -> bool:
        return all(importlib.util.find_spec(pkg) is not None for pkg in self.IMPORT_PACKAGES)

    def load(self) -> None:
        if self._loaded:
            return
        if not self.is_available():
            missing = tuple(
                pip
                for pkg, pip in zip(self.IMPORT_PACKAGES, self.PIP_PACKAGES or self.IMPORT_PACKAGES)
                if importlib.util.find_spec(pkg) is None
            )
            raise AdapterDependencyError(self.engine_id, missing or self.PIP_PACKAGES)
        logger.info(
            "Loading model", extra={"context": {"engine": self.engine_id, "device": self.device.value}}
        )
        with Stopwatch() as sw:
            self._load_impl()
        self._loaded = True
        logger.info(
            "Model loaded",
            extra={"context": {"engine": self.engine_id, "load_s": round(sw.elapsed_s, 2)}},
        )

    def unload(self) -> None:
        if not self._loaded:
            return
        self._unload_impl()
        self._model = None
        self._loaded = False

    def generate(self, request: GenerationRequest) -> GenerationResult:
        self._validate_inputs(request)
        self.load()
        output_path = request.output_path or self._temp_output_path(request)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with Stopwatch() as sw:
            result = self._generate_impl(request, output_path)
        result.generation_time_s = sw.elapsed_s
        result.engine_id = self.engine_id
        if not result.video_path.exists():
            raise ModelError(
                f"{self.engine_id} reported success but produced no video file",
                engine=self.engine_id,
                path=str(result.video_path),
            )
        return result

    # ------------------------------------------------------------------ helpers
    def _validate_inputs(self, request: GenerationRequest) -> None:
        for name in self.REQUIRED_INPUTS:
            if name not in _KNOWN_INPUTS:
                raise ModelError(f"Adapter declares unknown input {name!r}", engine=self.engine_id)
            value: Path | None = getattr(request, name)
            if value is None:
                raise ModelError(
                    f"{self.engine_id} requires {name} for its task",
                    engine=self.engine_id,
                    missing_input=name,
                )
            if not Path(value).exists():
                raise ModelError(
                    f"{self.engine_id} input file not found: {value}",
                    engine=self.engine_id,
                    missing_input=name,
                )

    def _temp_output_path(self, request: GenerationRequest) -> Path:
        stem = short_hash(
            f"{self.engine_id}|{request.scenario_id}|{request.source_image}|"
            f"{request.driving_audio}|{request.driving_video}"
        )
        return Path(tempfile.gettempdir()) / "aicp_avatar" / self.engine_id / f"{stem}.mp4"

    # ------------------------------------------------------------------ hooks
    def _load_impl(self) -> None:
        """Import heavy dependencies and load weights. Override per adapter."""
        raise NotImplementedError

    def _unload_impl(self) -> None:
        """Free model memory. Default: drop the reference (GC handles it)."""

    def _generate_impl(self, request: GenerationRequest, output_path: Path) -> GenerationResult:
        """Run inference, write the video to ``output_path``, return the result.

        ``generation_time_s`` and ``engine_id`` are overwritten by the base
        class; implementations fill the video properties.
        """
        raise NotImplementedError
