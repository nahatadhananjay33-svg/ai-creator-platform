"""Base adapter implementing the shared TTS/cloning lifecycle.

Concrete adapters supply:
- ``SPEC``: the :class:`ModelSpec` (single source of truth for metadata)
- ``CAPABILITIES``: declared :class:`EngineCapabilities`
- ``IMPORT_PACKAGES`` / ``PIP_PACKAGES``: dependency declarations
- ``_load_impl`` / ``_unload_impl`` / ``_synthesize_impl``: model calls

The base class owns: availability checks, lazy loading, timing, output-file
management, reference-audio validation, and voice-profile plumbing.
"""
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path
from typing import Any, ClassVar

from foundation.constants import Language
from foundation.exceptions import AdapterDependencyError, ModelError
from foundation.logging import get_logger
from foundation.model_manager import Device, ModelSpec, resolve_device
from foundation.shared_utils import Stopwatch, read_wav, short_hash
from voice_engine.interfaces import (
    EngineCapabilities,
    SynthesisRequest,
    SynthesisResult,
    TTSEngine,
    VoiceCloner,
    VoiceProfile,
)

logger = get_logger("voice_engine.adapters")


class BaseVoiceAdapter(TTSEngine, VoiceCloner):
    """Shared lifecycle for all voice model adapters."""

    SPEC: ClassVar[ModelSpec]
    CAPABILITIES: ClassVar[EngineCapabilities]
    #: Import names probed by :meth:`is_available` (e.g. ``("TTS",)``).
    IMPORT_PACKAGES: ClassVar[tuple[str, ...]] = ()
    #: pip package names shown in install hints (e.g. ``("coqui-tts",)``).
    PIP_PACKAGES: ClassVar[tuple[str, ...]] = ()

    def __init__(self, device: Device | str = Device.AUTO, config: dict[str, Any] | None = None) -> None:
        self.device = resolve_device(device)
        self.config: dict[str, Any] = config or {}
        self._loaded = False
        self._model: Any = None

    # ------------------------------------------------------------------ TTSEngine
    @property
    def engine_id(self) -> str:
        return self.SPEC.model_id

    @property
    def spec(self) -> ModelSpec:
        return self.SPEC

    @property
    def capabilities(self) -> EngineCapabilities:
        return self.CAPABILITIES

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

    def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        if not self.supports_language(request.language):
            raise ModelError(
                f"{self.engine_id} does not support language {request.language.value}",
                engine=self.engine_id,
                language=request.language.value,
            )
        self.load()
        output_path = request.output_path or self._temp_output_path(request)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with Stopwatch() as sw:
            self._synthesize_impl(request, output_path)
        wav = read_wav(output_path)
        return SynthesisResult(
            audio_path=output_path,
            sample_rate=wav.sample_rate,
            audio_duration_s=wav.duration_s,
            synthesis_time_s=sw.elapsed_s,
            engine_id=self.engine_id,
            request_text_chars=len(request.text),
        )

    # ------------------------------------------------------------------ VoiceCloner
    def create_voice_profile(
        self,
        reference_audio: Path,
        display_name: str,
        language_hint: Language | None = None,
    ) -> VoiceProfile:
        problems = self.validate_reference(reference_audio)
        if problems:
            raise ModelError(
                f"Reference audio rejected for {self.engine_id}: {'; '.join(problems)}",
                engine=self.engine_id,
                reference=str(reference_audio),
            )
        return VoiceProfile(
            profile_id=f"{self.engine_id}-{short_hash(str(reference_audio.resolve()))}",
            engine_id=self.engine_id,
            display_name=display_name,
            reference_audio=reference_audio,
            language_hint=language_hint,
        )

    def validate_reference(self, reference_audio: Path) -> list[str]:
        problems: list[str] = []
        if not reference_audio.exists():
            return [f"file not found: {reference_audio}"]
        try:
            wav = read_wav(reference_audio)
        except Exception as exc:  # noqa: BLE001
            return [f"unreadable WAV: {exc}"]
        min_ref = self.CAPABILITIES.min_reference_audio_s
        if min_ref is not None and wav.duration_s < min_ref:
            problems.append(
                f"reference too short: {wav.duration_s:.1f}s < required {min_ref:.1f}s"
            )
        if wav.duration_s > 60.0:
            problems.append("reference longer than 60s; trim to the cleanest 10-30s segment")
        peak = max(abs(s) for s in wav.samples) if len(wav.samples) else 0
        if peak >= 32767:
            problems.append("reference audio is clipped")
        if peak < 1000:
            problems.append("reference audio is near-silent")
        return problems

    # ------------------------------------------------------------------ hooks
    def _temp_output_path(self, request: SynthesisRequest) -> Path:
        stem = short_hash(f"{self.engine_id}|{request.language.value}|{request.text}")
        return Path(tempfile.gettempdir()) / "aicp_voice" / self.engine_id / f"{stem}.wav"

    def _load_impl(self) -> None:
        """Import heavy dependencies and load weights. Override per adapter."""
        raise NotImplementedError

    def _unload_impl(self) -> None:
        """Free model memory. Default: drop the reference (GC handles it)."""

    def _synthesize_impl(self, request: SynthesisRequest, output_path: Path) -> None:
        """Run inference and write a 16-bit PCM WAV to ``output_path``."""
        raise NotImplementedError
