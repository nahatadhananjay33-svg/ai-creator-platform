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

import tempfile
from pathlib import Path
from typing import Any, ClassVar

from foundation.exceptions import AdapterNotAvailableError, ModelError
from foundation.logging import get_logger
from foundation.model_manager import Device, ModelSpec, resolve_device
from foundation.model_manager.installer import VENVS_DIR, model_venv_python
from foundation.shared_utils import Stopwatch, short_hash

from avatar_engine.models.diagnostics import AdapterDiagnostic, diagnose
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
    #: Import names probed by :meth:`is_available` (checked inside the venv).
    IMPORT_PACKAGES: ClassVar[tuple[str, ...]] = ()
    #: pip package names shown in install hints.
    PIP_PACKAGES: ClassVar[tuple[str, ...]] = ()
    #: True for adapters that dispatch inference into an isolated per-model
    #: venv (the norm). Availability/CUDA are then probed in *that* interpreter,
    #: not the launcher. In-process adapters (e.g. mock) set this False.
    RUNS_IN_VENV: ClassVar[bool] = True

    def __init__(self, device: Device | str = Device.AUTO, config: dict[str, Any] | None = None) -> None:
        self.device = resolve_device(device)
        self.config: dict[str, Any] = config or {}
        self._loaded = False
        self._model: Any = None
        self._diag: AdapterDiagnostic | None = None

    # ------------------------------------------------------------------ venv resolution
    @property
    def venv_python(self) -> Path:
        """Interpreter that runs this adapter's inference/diagnostics.

        Defaults to the installer's per-model venv; overridable via
        ``config['venv_python']`` (used by tests and custom layouts).
        """
        override = self.config.get("venv_python")
        return Path(override) if override else model_venv_python(self.engine_id)

    @property
    def venv_dir(self) -> Path:
        override = self.config.get("venv_dir")
        if override:
            return Path(override)
        if self.config.get("venv_python"):
            return Path(self.config["venv_python"]).parent.parent
        return VENVS_DIR / self.engine_id

    def required_paths(self) -> list[Path]:
        """Filesystem artifacts (repo entrypoints, checkpoints) that must exist.

        Base declares none; adapters that run cloned repos / weights override.
        """
        return []

    # ------------------------------------------------------------------ AvatarGenerator
    @property
    def engine_id(self) -> str:
        return self.SPEC.model_id

    @property
    def spec(self) -> ModelSpec:
        return self.SPEC

    def diagnostics(self, force: bool = False) -> AdapterDiagnostic:
        """Full, structured runtime diagnostic (cached per instance).

        Replaces the old bare ``available=False``: reports the interpreter,
        venv, dependency imports, checkpoints, and CUDA state — probed inside
        the adapter's own venv.
        """
        if self._diag is None or force:
            self._diag = diagnose(
                self.engine_id,
                packages=self.IMPORT_PACKAGES,
                required_paths=self.required_paths(),
                expected_device=self.device.value,
                runs_in_venv=self.RUNS_IN_VENV,
                venv_python=self.venv_python,
                venv_dir=self.venv_dir,
            )
        return self._diag

    def is_available(self) -> bool:
        return self.diagnostics().available

    @property
    def actual_device(self) -> str:
        """Device inference will actually run on in this adapter's venv
        ('cuda' only when requested *and* usable there, else 'cpu')."""
        return self.diagnostics().actual_device

    def load(self) -> None:
        if self._loaded:
            return
        diag = self.diagnostics()
        if not diag.available:
            # AdapterNotAvailableError -> the benchmark records the case SKIPPED
            # with this exact reason instead of a generic failure.
            raise AdapterNotAvailableError(
                f"{self.engine_id} unavailable: {diag.reason}",
                adapter=self.engine_id,
                python_executable=diag.python_executable,
                venv_exists=diag.venv_exists,
                missing_packages=[p.name for p in diag.packages if not p.importable],
                missing_paths=[ps["path"] for ps in diag.required_paths if not ps["exists"]],
            )
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
